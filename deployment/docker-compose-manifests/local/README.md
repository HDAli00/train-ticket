# Train-Ticket 1.0 — local Docker Compose deployment

A single-machine deployment of the full train-ticket system (45 microservices
+ UI) using the pre-built upstream `codewisdom/ts-*:1.0.x` images — no
Kubernetes and no source build required.

The older compose files in the parent directory (`quickstart-docker-compose.yml`,
and the repo-root `docker-compose.yml`) predate the 1.0 architecture: they are
missing Nacos and RabbitMQ, start unconfigured MySQL/Mongo containers, and set
none of the environment variables the 1.0 services read — which is why every
service crash-loops when you use them. This directory replaces them for local use.

## What it runs

| Component | Image | Notes |
|---|---|---|
| Nacos (service discovery) | `nacos/nacos-server:v2.1.0` | standalone mode, embedded storage, `:8848` |
| MySQL (shared, all-in-one) | `mysql:5.7` | db `ts`, user `ts` / `Ts_123456`, `max_connections=1000` |
| RabbitMQ | `rabbitmq:3.10` | used by order/preserve/food/rebook/etc. |
| 45 ts-* services + UI | `codewisdom/ts-*:1.0.x` | same images/tags as the k8s quickstart |

Service list, images, ports and env wiring are **generated** from
`deployment/kubernetes-manifests/quickstart-k8s/yamls/deploy.yaml.sample` by
`hack/gen-local-compose.py`, mirroring what `make deploy` does on Kubernetes
(the `nacos`/`rabbitmq` ConfigMaps and per-service `ts-*-mysql` Secrets become
container environment variables). To regenerate after upstream changes:

```bash
python3 hack/gen-local-compose.py
```

## Requirements

- Docker with the compose plugin
- ~14 GB free RAM (each Java service runs with `-Xmx200m`, capped at 700 MB)
- ~15 GB free disk for images

## Usage

```bash
cd deployment/docker-compose-manifests/local
./up.sh          # staged startup: infra -> service waves -> gateway -> UI
./up.sh status   # per-service health
./up.sh down     # tear everything down (removes volumes)
```

Do **not** use a bare `docker compose up -d` on a small machine — starting 46
JVMs simultaneously CPU-starves the host; `up.sh` brings them up in dependency
waves and waits for health between waves. First full startup takes roughly
10–20 minutes depending on the machine.

## Entry points

- Web UI: <http://localhost:8080>
- API gateway: <http://localhost:18888>
- Nacos console: <http://localhost:8848/nacos>

Default test user: `fdse_microservice` / `111111` (created by ts-auth-service
and ts-user-service on first start). Admin user: `admin` / `222222`.

## Smoke test

```bash
# login through the gateway
curl -s -X POST http://localhost:18888/api/v1/users/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"fdse_microservice","password":"111111"}'

# query tickets Shang Hai -> Su Zhou
curl -s -X POST http://localhost:18888/api/v1/travelservice/trips/left \
  -H 'Content-Type: application/json' \
  -d '{"startPlace":"Shang Hai","endPlace":"Su Zhou","departureTime":"2026-07-10"}'
```

## Troubleshooting

- **A service is restarting**: `docker compose logs <name> --tail 50`. The
  usual causes are Nacos not healthy yet (services retry and recover on their
  own) or host memory pressure.
- **`Too many connections` from MySQL**: the shared MySQL already runs with
  `max_connections=1000`; if you still hit it, some service is leaking pools —
  restart that service.
- **UI loads but API calls fail**: the UI proxies everything to
  `ts-gateway-service:18888`; check the gateway and the target service are
  healthy in `./up.sh status`.
