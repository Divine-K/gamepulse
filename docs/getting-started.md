# Getting started

Everything here is free software and runs on your own machine. The steps are written for macOS and Linux; on Windows use WSL.

## 1. Prerequisites

| Tool | Version | Used for |
|---|---|---|
| Docker (Docker Desktop on macOS and Windows) | recent | PostgreSQL, Redis, and the production stack |
| Python | 3.13 | The API and its tests |
| Node.js | 24 | The dashboard and its tests |
| Google Chrome | recent | The Playwright end-to-end tests (they drive the installed Chrome) |

On macOS: `brew install python@3.13 node@24 git`, plus Docker Desktop.

## 2. Configure

All settings live in one `.env` file at the repository root, which the API, Docker Compose and the tests all read. It is git-ignored: never commit it.

```bash
cp .env.example .env
openssl rand -hex 32        # paste the output as SECRET_KEY
openssl rand -hex 16        # use as the PostgreSQL password
```

Edit `.env`:

- `SECRET_KEY`: the first random value (at least 32 characters).
- `POSTGRES_PASSWORD`: the second random value, and put the same value in `DATABASE_URL` (`postgresql+psycopg://gamepulse:<password>@localhost:5432/gamepulse`).

The remaining defaults work for local development.

## 3. Start PostgreSQL and Redis

```bash
docker compose up -d
docker compose ps           # both services should say "healthy"
```

## 4. Start the API

```bash
cd backend
python3.13 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
alembic upgrade head        # create the tables
uvicorn app.main:app --reload
```

Check it: <http://localhost:8000/health> returns `{"status":"ok"}`, and <http://localhost:8000/api/v1/health/ready> reports PostgreSQL and Redis. The interactive API reference is at <http://localhost:8000/docs> (it is switched off when `APP_ENV=production`).

## 5. Start the dashboard

```bash
cd frontend
npm install
npm run dev
```

Open <http://localhost:5173>. The dashboard talks to `http://localhost:8000` by default; set `VITE_API_BASE_URL` to point it elsewhere.

## 6. Take the tour

1. **Create an account** on the sign-up page.
2. **Create a game** on the Games page. Six achievements are added automatically (Champion is switched off until you enable it).
3. Open **Simulator** and press **Run a quick demo**. A test player registers, plays a session, scores, unlocks achievements and finishes, and the **Live feed** shows every event as it happens. Check Overview, Players, Sessions, Leaderboards and Analytics afterwards.
4. Open the game and **create an API key** (the key is shown once). Paste it into **API Playground** to send real requests, or connect your own game with the [integration guide](integration-guide.md).

## 7. Run the tests

| Suite | Command | Notes |
|---|---|---|
| Backend | `cd backend && pytest -q` | Needs `docker compose up -d`. Uses its own `gamepulse_test` database and Redis DB 15, never your data. |
| Backend lint | `cd backend && ruff check . && ruff format --check .` | |
| Frontend | `cd frontend && npm run lint && npm test && npm run build` | ESLint, Vitest, then type-check and build |
| End to end | `cd frontend && npm run e2e` | Starts an isolated API on :8100 and the UI on :5174, then drives Chrome |
| Smoke test | `python backend/scripts/smoke.py http://localhost:8000 --api-only` | REST, WebSocket and analytics against any running API |

Details and results are in [testing](testing.md).

## 8. Run the production stack in Docker

This builds the same two images used in deployment: the API (non-root, applies migrations on start) and the dashboard (nginx with a strict Content-Security-Policy, proxying `/api` and the WebSocket to the API).

```bash
cp .env.production.example .env.production      # then replace every value
openssl rand -hex 32                            # SECRET_KEY
openssl rand -hex 24                            # POSTGRES_PASSWORD
docker compose --env-file .env.production -f docker-compose.prod.yml up -d --build
python backend/scripts/smoke.py http://localhost:8080
```

Open <http://localhost:8080>. Only that port is published; PostgreSQL, Redis and the API stay on a private Docker network. The API refuses to start with `APP_ENV=production` if `SECRET_KEY` still contains the `change-me` placeholder. Stop it with `docker compose --env-file .env.production -f docker-compose.prod.yml down` (add `-v` to delete the data volumes).

To put it on the internet for free, follow [deploy-free-tiers](deploy-free-tiers.md). Configuration reference: [deployment](deployment.md).

## Demo data and screenshots

To fill a dashboard with believable data, play the example game against any running API:

```bash
export GAMEPULSE_KEY=gp_xxxxxxxxxxxx_...        # an API key for one of your games
python examples/surfer/play.py --players 36 --rounds 4 --seed 11
```

Everything the example creates is stamped "now", so charts show a single day and sessions last a moment. To make the charts look like a game that has been running for two weeks, spread that game's timestamps:

```bash
cd backend && python scripts/seed_demo.py --game-id <game uuid> --days 14
```

The data is still real API output; the script only moves each player's registration and each session (with its events, scores and unlocks) back in time, keeps every ordering valid, and gives finished sessions a duration of 2 to 25 minutes. It edits one game, and refuses to run when `APP_ENV=production`.

The screenshots in the README were produced by `frontend/scripts/screenshots.mjs`, which does all of the above on a local stack with a throwaway account, then photographs each page in Chrome:

```bash
cd frontend && node scripts/screenshots.mjs      # API on :8000 and dashboard on :5173 must be running
```

## Troubleshooting

| Symptom | Likely cause and fix |
|---|---|
| `connection refused` on port 5432 or 6379 | Docker is not running or the services are not up: `docker compose up -d`, then `docker compose ps`. |
| `password authentication failed` | `POSTGRES_PASSWORD` and the password inside `DATABASE_URL` differ. If the volume already exists from an earlier password, run `docker compose down -v` (this deletes local data) and start again. |
| `alembic` cannot find the database | Run it from `backend/` with the virtualenv active, and check `DATABASE_URL` in the root `.env`. |
| `Refusing to start ... SECRET_KEY` | Production mode needs a real random `SECRET_KEY`: `openssl rand -hex 32`. |
| Dashboard shows a network or CORS error | The API is not running on the address the dashboard uses, or, when they are on different origins, `CORS_ORIGINS` (a JSON list such as `["http://localhost:5173"]`) does not include the dashboard's address. |
| `address already in use` | Another process holds port 8000 or 5173. Stop it, or pass `--port` to uvicorn and set `VITE_API_BASE_URL` to match. |
| Playwright cannot launch the browser | The suite drives the installed Google Chrome; install Chrome, or change `channel` in `frontend/playwright.config.ts`. |
| First request to the deployed API takes about a minute | Free hosting sleeps the API when idle. It wakes on the next request. |
