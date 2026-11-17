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
(Filled in as phases land.)

## Current phase
Phase 1: Environment and GitHub setup.

## Completed milestones
- Environment: Homebrew, Node, Git, gh, Python 3.13, Docker Desktop, VS Code installed; GitHub CLI authenticated.

## Pending milestones
Phase 1 remainder (venv, Vite app, Docker Compose) → 2 Architecture/DB design → 3 Backend foundation → 4 Auth and games → 5 Players and sessions → 6 Scores, leaderboards, achievements → 7 Real-time → 8 Frontend foundation → 9 Dashboard → 10 API playground and simulator → 11 QA → 12 Docker/deploy → 13 Docs.

## Architectural decisions
- Postgres and Redis run via Docker Compose in development.
- Developers authenticate with JWT; games authenticate with hashed, rotatable API keys.
