# PROJECT.md — GamePulse project handbook

## Overview
GamePulse is a multi-tenant game backend and analytics platform. Developers register games, get game-scoped API keys, and external games send players, sessions, scores and events over REST. A React dashboard shows live and historical analytics. Portfolio-grade: clean architecture, tests, docs, real GitHub history.

## Architecture
External games → REST (X-API-Key) → FastAPI → services → repositories → PostgreSQL + Redis → REST/WebSocket → React dashboard.
- Layering: `api → services → repositories → models`. Business rules live in services.
- Multi-tenancy: developer owns games; every player/session/score/event/achievement row carries `game_id`. Ownership and game scope are enforced in the backend, never only in the UI.
- Redis: caching, active-session tracking (TTL), pub/sub for WebSockets, rate limits, idempotency.
- Analytics are computed from real DB rows. Seed data is for dev/demo only.

## Tech stack
Backend: Python 3.13, FastAPI, SQLAlchemy, Alembic, Pydantic, Pytest, HTTPX, Ruff.
Frontend: React, TypeScript, Vite, Tailwind, Motion, Recharts, React Router, TanStack Query, React Hook Form, Zod, Vitest, Playwright, ESLint, Prettier.
Infra: PostgreSQL, Redis, Docker Compose, GitHub Actions.

## Folder structure
`backend/app/{api,core,models,schemas,services,repositories,websocket}`, `backend/tests`, `backend/alembic`, `frontend/src/{components,pages,layouts,hooks,services,types,context,assets}`, `docs/`, `docker/`, `.github/workflows/`.

## Coding standards
- Python: PEP 8, type hints, Ruff. No giant files; small modules.
- TypeScript: strict mode, ESLint + Prettier, reusable components.
- No unnecessary dependencies or abstractions. No fake production analytics. No placeholder features presented as finished.

## Naming conventions
Python snake_case / PascalCase classes; TS camelCase / PascalCase components; DB tables plural snake_case; API paths under `/api/v1`.

## Git conventions
Conventional commits (`feat:`, `fix:`, `chore:`, `docs:`, `test:`). Feature branches for substantial work. Before each commit: tests, lint, diff review, secret check. Never force-push without explicit permission. Push after every milestone and verify.

## Testing requirements
Pytest + HTTPX for API/auth/session workflows, tenant-isolation tests required. Vitest + RTL for components. Playwright for E2E.

## Security rules
Never commit secrets (`.env` is gitignored). Hash passwords and API keys; show API key secret once. Validate all input. Enforce authorization in the backend. Redact secrets in logs and UI.

## Development commands
```bash
docker compose up -d                                   # Postgres + Redis (repo root)
cd backend && source .venv/bin/activate                # Python env
pip install -r requirements-dev.txt                    # backend deps
ruff check . && ruff format .                          # lint + format (backend/)
pytest -q                                              # backend tests (uses isolated gamepulse_test DB + Redis DB 15; needs docker compose up)
uvicorn app.main:app --reload                          # API at :8000, docs at /docs
alembic upgrade head                                   # apply migrations
alembic revision --autogenerate -m "message"          # new migration
cd frontend && npm install && npm run dev              # dashboard
```
Design docs: `docs/architecture.md`, `docs/database-schema.md`, `docs/api-guide.md`.

## Cost rule (hard constraint)
Everything must be free: open-source libraries, free tiers only, no paid APIs or subscriptions, no paid AI/LLM calls in the app. Before adopting any hosted service (especially for Phase 12 deployment), confirm it has a genuinely free tier and ask the user if it needs a card on file. Docker Desktop is free for personal use; GitHub Actions is free within limits.

## Current phase
Phase 6 complete (scores, leaderboards, achievements). Next: Phase 7, real-time infrastructure.

## Completed milestones
- Phase 1: Homebrew, Node, Git, gh, Python 3.13, Docker Desktop, VS Code installed; GitHub CLI authenticated; repo `Divine-K/gamepulse` (private); backend venv, Vite frontend, Postgres and Redis via Docker Compose.
- Phase 2: `docs/architecture.md` (diagrams, ADR-001 to 013), `docs/database-schema.md` (ER diagram, constraints), `docs/api-guide.md` (conventions, endpoint plan).

- Phase 3: FastAPI app factory, settings, async SQLAlchemy, Redis client, Alembic (async), JSON logging with request ids, error envelope, liveness and readiness probes, 9 passing tests.

- Phase 4: developer register/login (Argon2id, JWT), profile, role-based access, games CRUD (soft delete), API keys (hashed, shown once, rotate/revoke), `X-API-Key` game auth, Redis rate limiting on auth, first Alembic migration, isolated test DB, 49 tests including cross-tenant isolation.

- Phase 5: players (idempotent registration, stats), session lifecycle (start with Idempotency-Key, heartbeat, end, abandon via lazy reclaim + background reaper), history, dashboard player/session views, composite-FK tenant integrity, row locking, 80 tests.

- Phase 6: score ledger + live session scores, metric-based leaderboards (competition ranking, search, order, min_value, `category:<name>` metrics with periods, player rank), configurable achievement engine (5 condition types, default set seeded per game, DB-enforced no duplicates), dashboard achievement management and unlock stats, 108 tests.

## Pending milestones
7 Real-time → 8 Frontend foundation → 9 Dashboard → 10 API playground and simulator → 11 QA → 12 Docker/deploy → 13 Docs.

## Architectural decisions
- Postgres and Redis run via Docker Compose in development.
- Developers authenticate with JWT; games authenticate with hashed, rotatable API keys.
