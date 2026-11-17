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

Setup instructions will be added as each phase lands. See `PROJECT.md` for the project handbook and roadmap.
