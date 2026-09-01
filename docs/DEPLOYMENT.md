# Production Deployment

## Prerequisites

- Docker + Docker Compose (Compose v2).
- Strong random secrets in `.env` (see `.env.example` and `docs/ENCRYPTION.md`).
- A TLS certificate for HTTPS/WSS (e.g. Let's Encrypt via certbot, or a
  managed load balancer).

## Quick Production Start

```bash
cp .env.example .env
# 1. Edit .env: strong random secrets, PUBLIC_ORIGIN=https://your.domain,
#    USE_HTTPS=true, admin password.
# 2. Place a certificate/key at /etc/ssl/cert.pem and /etc/ssl/key.pem
#    (or set TLS_CERT_PATH / TLS_KEY_PATH in .env).
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

The backend runs `alembic upgrade head` and `python -m scripts.seed` on
startup (both idempotent), then launches uvicorn.

## Hardening Checklist

- **HTTPS/WSS**: TLS terminates at nginx (`nginx.prod.conf`). `USE_HTTPS=true`.
- **Secrets**: never commit `.env`. Use a secret manager (Vault, Docker
  secrets, AWS/K8s secrets) and inject via env vars.
- **Non-root containers**: the backend/frontend images run as an unprivileged
  user.
- **Resource limits**: `docker-compose.prod.yml` sets `mem_limit`/`cpus`.
- **Security headers**: the backend sets `X-Content-Type-Options`,
  `X-Frame-Options`, `Referrer-Policy`, and a restrictive CSP.
- **Rate limiting**: login and API routes are rate-limited in Redis.
- **File validation**: MIME allow-list + size cap + streamed upload (no full
  in-memory files).
- **Monitoring**: structured JSON logs; optional OpenTelemetry export.

## OpenTelemetry / Prometheus / Grafana

Set `OTEL_EXPORTER_ENDPOINT` to a collector (e.g. an OpenTelemetry Collector
feeding Prometheus + Grafana). The backend is instrumented with OpenTelemetry
hooks (`opentelemetry-instrumentation-fastapi`) for request metrics.

## Kubernetes Migration

The services are stateless and horizontally scalable:

| Service | Notes |
|---------|-------|
| Backend | scale horizontally; add more replicas — Redis Pub/Sub fans out events |
| Frontend | stateless; scale horizontally behind a load balancer |
| Postgres | managed instance (RDS/Cloud SQL) or operator-managed |
| Redis | managed instance or operator-managed (pub/sub + presence) |
| Media | switch to S3/MinIO (`MEDIA_STORAGE_BACKEND=s3`) so replicas share storage |
| Nginx | replace with an Ingress / LB that terminates TLS and proxies `/api/` + `/ws/` |

Represent the services as Kubernetes manifests (Deployment + Service), mount
secrets via Kubernetes Secrets, and point `DATABASE_URL`/`REDIS_URL`/S3 at the
managed services.

## Health Checks

- `/api/v1/health` verifies DB + Redis connectivity.
- Compose healthchecks gate `depends_on` so the backend waits for Postgres and
  Redis.