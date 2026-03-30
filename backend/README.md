# Jarvis Backend

FastAPI + PostgreSQL (local) + Redis + Celery.

## Local development

1. Copy `.env.example` to `.env` and set secrets. Ensure Postgres is running locally and `DATABASE_URL` points at it (e.g. `...@localhost:5432/...`).
2. `docker compose up -d redis` (from repo root) or run Redis however you prefer.
3. `pip install -e ".[dev]"` and `alembic upgrade head`
4. `uvicorn app.main:app --reload`
5. In separate terminals: `celery -A app.workers.celery_app worker` and `celery -A app.workers.celery_app beat`

Or run API + workers + Redis in Docker (Postgres stays on the host): `docker compose up --build` from the repo root.
