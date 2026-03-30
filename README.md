# Jarvis — Voice-Driven Smart Task Scheduler (Phase 1)

Monorepo: **FastAPI** backend (`backend/`) and **Expo** mobile app (`mobile/`).

## Prerequisites

- **PostgreSQL** on your machine (create a database and user, or adjust `DATABASE_URL`)
- Docker for **Redis + API + Celery** (Postgres is not run in Compose)
- Node.js 20+ for the mobile app
- Python 3.10+ if running the API locally without Docker

## Backend

1. Copy `backend/.env.example` to `backend/.env` and set `SECRET_KEY`, `OPENAI_API_KEY`, and `DATABASE_URL` for **local** Postgres (e.g. `...@localhost:5432/...`). Docker Compose overrides `DATABASE_URL` to `host.docker.internal` so containers can reach your host DB.
2. Start Redis and the app stack (containers use `host.docker.internal` to reach Postgres on the host by default):

```bash
docker compose up --build
```

3. Run migrations (first time):

```bash
cd backend && pip install -e ".[dev]"
export DATABASE_URL=postgresql+asyncpg://jarvis:jarvis@localhost:5432/jarvis
alembic upgrade head
```

Or `docker compose exec api alembic upgrade head` (uses host Postgres via `host.docker.internal` inside the container).

API: `http://localhost:8000` — OpenAPI docs at `/docs`.

## Mobile

```bash
cd mobile
cp .env.example .env   # set EXPO_PUBLIC_API_URL, e.g. http://YOUR_LAN_IP:8000
npm start
```

Use a device or simulator on the same network as the API when testing against a physical machine.

## Architecture notes

- **Orchestrator** (`app/services/orchestrator.py`) parses natural language via OpenAI JSON, dispatches to **Task Service**, and uses a second LLM pass for task matching when needed.
- **Inference** (`app/services/inference.py`) is rule-based only (priority, reminders, points, penalties).
- **Day close** (`POST /day/close`) marks remaining same-day pending tasks as missed; tasks are not marked missed until the day is closed (or auto-close after midnight + grace).
- **Celery** handles per-task reminders, morning summary, EOD prompt, and auto-close sweeps.
