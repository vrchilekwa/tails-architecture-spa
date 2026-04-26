# Tails Target-State API (Python)

FastAPI backend with:
- PostgreSQL persistence via SQLAlchemy
- Kafka producer/consumer integration via `aiokafka`
- JWT auth and Google OIDC stub flow
- Docker + docker-compose one-command startup

## Quick start

```bash
docker compose up --build
```

API docs: `http://localhost:8000/docs`

## Main endpoints

- `POST /auth/signup`
- `POST /auth/login`
- `GET /auth/google/start`
- `GET /auth/google/callback?code=...` (stub)
- `POST /dogs`
- `GET /dogs/{dog_id}`
- `POST /plans/quote`
- `POST /subscriptions`
- `POST /subscriptions/{subscription_id}/pause`
- `POST /checkout`
- `GET /orders?customer_id=...`

## Auth usage

1. Create token via signup/login.
2. Send header: `Authorization: Bearer <token>`.

## Notes

- Google OIDC flow is intentionally a stub to show integration points.
- DB tables are created automatically at startup.
- Kafka startup failures are non-fatal; app still runs with warning logs.
