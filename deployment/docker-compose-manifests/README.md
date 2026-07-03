> Docker Compose

* **For the current 1.0 services, use [`local/`](./local/) — `cd local && ./up.sh`.**
  It runs the full system (Nacos + MySQL + RabbitMQ + all 45 services + UI)
  from the pre-built `codewisdom` images with the correct environment wiring.

* `quickstart-docker-compose.yml` and `docker-compose-with-jaeger.yml` predate
  the 1.0 architecture (no Nacos/RabbitMQ, unconfigured databases, no service
  env vars) and are kept only as reference — services started from them will
  crash-loop.
