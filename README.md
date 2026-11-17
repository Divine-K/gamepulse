# GamePulse

**Game Backend & Analytics Platform** — a multi-tenant backend that lets game developers plug their games into shared player management, session tracking, leaderboards, achievements, event ingestion and analytics, with a real-time developer dashboard.

> Status: early development (Phase 1: environment and project setup).

## Architecture (planned)

```
External games ──REST + API key──┐
                                 ▼
React dashboard ──JWT REST/WS──► FastAPI ─► Services ─► Repositories ─► PostgreSQL
                                    └────────────────────► Redis (cache, live sessions, pub/sub)
```

## Tech stack

Python, FastAPI, SQLAlchemy, Alembic, PostgreSQL, Redis, WebSockets, JWT, React, TypeScript, Vite, Tailwind CSS, Docker, Pytest, Playwright.

## Repository layout

| Path | Purpose |
|---|---|
| `backend/` | FastAPI application, tests, migrations |
| `frontend/` | React + TypeScript developer dashboard |
| `docs/` | Architecture, schema, API and deployment docs |
| `docker/` | Dockerfiles and container config |
| `.github/workflows/` | CI pipelines |

## Getting started

Quick start (development):

```bash
cp .env.example .env            # then set real secrets
docker compose up -d            # PostgreSQL + Redis
cd backend && python3.13 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt && alembic upgrade head
uvicorn app.main:app --reload   # API on http://localhost:8000 (docs at /docs)
cd ../frontend && npm install && npm run dev   # dashboard on http://localhost:5173
```

Full setup instructions will be expanded as each phase lands. See `PROJECT.md` for the project handbook and roadmap.
