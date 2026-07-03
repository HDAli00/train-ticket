#!/bin/bash
# Staged startup for the local train-ticket docker-compose stack.
#
# Starting all ~46 services at once thrashes small machines (every Spring Boot
# app initializes simultaneously), so this brings the system up in dependency
# waves: infrastructure -> core data services -> aggregation services ->
# admin/gateway -> UI.
#
# Usage: ./up.sh            start everything
#        ./up.sh status     show per-service health
#        ./up.sh down       stop and remove everything

set -euo pipefail

DIR=$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )
COMPOSE="docker compose -f $DIR/docker-compose.yml"

# Wave 1: leaf data services (only need nacos/mysql/rabbitmq)
WAVE1="ts-verification-code-service ts-auth-service ts-user-service ts-station-service ts-train-service ts-config-service ts-price-service ts-route-service ts-contacts-service ts-order-service ts-order-other-service ts-assurance-service"
# Wave 2: services building on wave 1
WAVE2="ts-basic-service ts-seat-service ts-travel-service ts-travel2-service ts-ticket-office-service ts-security-service ts-food-service ts-train-food-service ts-station-food-service ts-consign-price-service ts-consign-service ts-news-service"
# Wave 3: aggregation / business-flow services
WAVE3="ts-payment-service ts-inside-payment-service ts-notification-service ts-cancel-service ts-execute-service ts-preserve-service ts-preserve-other-service ts-rebook-service ts-route-plan-service ts-travel-plan-service ts-wait-order-service ts-delivery-service ts-food-delivery-service ts-voucher-service ts-avatar-service"
# Wave 4: admin panel + gateway
WAVE4="ts-admin-basic-info-service ts-admin-order-service ts-admin-route-service ts-admin-travel-service ts-admin-user-service ts-gateway-service"

wait_healthy() {
  # wait_healthy <timeout-seconds> <service...>
  local timeout=$1; shift
  local deadline=$(( $(date +%s) + timeout ))
  local pending=("$@")
  while (( ${#pending[@]} > 0 )); do
    local still=()
    for s in "${pending[@]}"; do
      state=$($COMPOSE ps --format '{{.Health}}' "$s" 2>/dev/null || true)
      if [[ "$state" != "healthy" ]]; then still+=("$s"); fi
    done
    pending=("${still[@]+"${still[@]}"}")
    if (( ${#pending[@]} == 0 )); then break; fi
    if (( $(date +%s) > deadline )); then
      echo "WARNING: timed out waiting for: ${pending[*]} (continuing anyway)" >&2
      break
    fi
    sleep 5
  done
}

case "${1:-up}" in
  down)
    $COMPOSE down -v
    exit 0
    ;;
  status)
    $COMPOSE ps --format 'table {{.Name}}\t{{.Status}}'
    exit 0
    ;;
  up)
    echo "==> [1/6] Infrastructure: mysql, nacos, rabbitmq"
    $COMPOSE up -d ts-mysql nacos rabbitmq
    wait_healthy 300 ts-mysql nacos rabbitmq
    echo "==> [2/6] Wave 1: core data services"
    $COMPOSE up -d $WAVE1
    wait_healthy 600 $WAVE1
    echo "==> [3/6] Wave 2: domain services"
    $COMPOSE up -d $WAVE2
    wait_healthy 600 $WAVE2
    echo "==> [4/6] Wave 3: aggregation services"
    $COMPOSE up -d $WAVE3
    wait_healthy 600 $WAVE3
    echo "==> [5/6] Wave 4: admin + gateway"
    $COMPOSE up -d $WAVE4
    wait_healthy 600 $WAVE4
    echo "==> [6/6] UI dashboard"
    $COMPOSE up -d ts-ui-dashboard
    wait_healthy 120 ts-ui-dashboard
    echo
    $COMPOSE ps --format 'table {{.Name}}\t{{.Status}}'
    echo
    echo "Train-ticket is up: UI http://localhost:8080  API gateway http://localhost:18888  Nacos http://localhost:8848/nacos"
    ;;
  *)
    echo "usage: $0 [up|status|down]" >&2
    exit 1
    ;;
esac
