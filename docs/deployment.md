# Deployment guide

GamePulse ships as two container images plus PostgreSQL and Redis. Everything here uses free software and, in the hosting section, only options that have a free tier. Nothing has been deployed yet: choosing a host means creating an account, so that is your call (see "What I need from you").

## What gets deployed

```
Browser --HTTPS--> nginx (dashboard image) --/api, WebSocket--> API (uvicorn) --> PostgreSQL
                                                                         \--> Redis
```

- **Dashboard image** (`frontend/Dockerfile`): the production build served by nginx with a strict Content-Security-Policy and security headers. It proxies `/api/` (including the live WebSocket) to the API, so the browser only ever talks to one origin and no CORS configuration is needed.
- **API image** (`backend/Dockerfile`): non-root, applies database migrations on start, then runs uvicorn with several workers. Real client IPs come from `X-Forwarded-For` (`FORWARDED_ALLOW_IPS`), so rate limits work behind the proxy.
- **PostgreSQL 17** (source of truth) and **Redis 7** (cache, live tracking, pub/sub). Redis can lose its data safely: the active-player index is rebuilt from PostgreSQL at startup and caches refill on demand.

## Run the production stack locally

```bash
cp .env.production.example .env.production        # then edit: real secrets
openssl rand -hex 32                              # use as SECRET_KEY
openssl rand -hex 24                              # use as POSTGRES_PASSWORD
docker compose --env-file .env.production -f docker-compose.prod.yml up -d --build
python backend/scripts/smoke.py http://localhost:8080   # REST + WebSocket + headers check
```

Open http://localhost:8080. Only that port is published; the database, Redis and API are on a private Docker network. The API refuses to start with `APP_ENV=production` if `SECRET_KEY` still contains the `change-me` placeholder.

Verified: the full Playwright suite (21 tests) passes against these containers, and the same check runs in CI.

## Configuration

| Variable | Required | Meaning |
|---|---|---|
| `SECRET_KEY` | yes | Signs login tokens. At least 32 characters; random; never reuse the development one |
| `DATABASE_URL` | yes | `postgresql+psycopg://user:password@host:5432/db` (the compose file builds it from the `POSTGRES_*` values) |
| `REDIS_URL` | no | Defaults to `redis://localhost:6379/0` |
| `APP_ENV` | no | `production` disables the interactive API docs and enables extra checks |
| `CORS_ORIGINS` | only if the dashboard is on a different origin | JSON list, for example `["https://app.example.com"]` |
| `VITE_API_BASE_URL` | build argument | Empty means same origin (default). Set an absolute URL when the dashboard is hosted separately |
| `AUTH_RATE_LIMIT_PER_MINUTE`, `GAME_API_RATE_LIMIT_PER_MINUTE` | no | Defaults 10 and 600 |
| `WEB_CONCURRENCY` | no | API worker processes (default 2) |
| `PORT` | no | Port the API listens on (many hosts set this for you) |

## CI

`.github/workflows/ci.yml` runs on every push and pull request: backend lint and tests (real PostgreSQL and Redis), frontend lint, type-check, tests and build, the Playwright suite on an isolated stack, a Docker job (build the images, bring the stack up, smoke test, run the browser suite against it) and a dependency audit. GitHub Actions is free for public repositories; private repositories get a monthly allowance of free minutes, and a full run uses roughly 15 to 20 of them.

## Free hosting options (researched 2026-11-17)

Free tiers change often and the figures below come from provider pages and third-party write-ups. Re-check the provider's own page before signing up.

| Need | Option | Free allowance | Catches |
|---|---|---|---|
| Static dashboard | [Cloudflare Pages](https://developers.cloudflare.com/pages/platform/limits) | Unlimited sites, requests and bandwidth; 500 builds per month | Needs the dashboard built with an absolute `VITE_API_BASE_URL` and `CORS_ORIGINS` set on the API |
| PostgreSQL | [Neon](https://neon.com/faqs/free-plan-limits-and-quotas) | Permanent free plan, no card; about 1 GB per project, 100 compute-hours per month; scales to zero when idle | First request after idle is slower; compute suspends if the monthly limit is reached |
| Redis | [Upstash](https://upstash.com/pricing/redis) | About 256 MB and 500,000 commands per month, permanent | Not verified that `PSUBSCRIBE` (used by the live-event hub) works on the free tier. Each game action uses several commands |
| Redis (alternative) | [Render Key Value](https://render.com/docs/free) | 25 MB, one per workspace | Data is lost on restart (fine for GamePulse: it rebuilds) |
| API container | [Render](https://render.com/docs/free) free web service | 750 instance hours per month | Sleeps after 15 minutes idle (about a minute to wake) and the free PostgreSQL there expires after 30 days, so pair it with Neon. The first request and any open live stream drop on sleep |
| API container | [Koyeb](https://www.koyeb.com/docs/faqs/pricing) | One small instance (512 MB) | Recent reports say a card with a temporary authorisation hold is now required: confirm before relying on it |
| Whole stack on one VM | [Oracle Cloud Always Free](https://docs.oracle.com/en-us/iaas/Content/FreeTier/resourceref.htm) | Up to 4 Arm cores and 24 GB RAM, permanent | Account creation needs a payment card for verification, Arm capacity is sometimes unavailable, and idle instances can be reclaimed. Runs `docker-compose.prod.yml` as is |

### Two realistic zero-cost paths

1. **One VM (highest fidelity).** Oracle Always Free VM running `docker-compose.prod.yml`, with a free Cloudflare Tunnel or Caddy in front for HTTPS. The whole stack behaves exactly as tested. Cost: nothing, but it needs a verification card.
2. **Split free tiers (no always-on server), prepared:** step-by-step in [deploy-free-tiers.md](deploy-free-tiers.md). Dashboard on Cloudflare Pages, API container on Render, PostgreSQL on Neon, and a small free Redis. Everything stays free, but the API sleeps when idle, so the first visit after a quiet period is slow and the live stream reconnects.

For a portfolio demo, option 2 sleeping is acceptable if the README says so. For a demo that must respond instantly, option 1.

## Deployment checklist

1. HTTPS everywhere; HSTS at the TLS edge.
2. Generate a real `SECRET_KEY`; keep `.env.production` out of git (it is ignored).
3. Set `APP_ENV=production`, and `CORS_ORIGINS` only if the dashboard is on another origin.
4. Keep PostgreSQL and Redis off the public internet.
5. Back up PostgreSQL (free tiers often have no backups: export with `pg_dump` on a schedule).
6. Run migrations once per release. The API image does this on start, which is safe for a single instance; with several instances run `alembic upgrade head` as a separate step first.
7. After deploying, run `python backend/scripts/smoke.py https://your-domain` and the browser suite with `E2E_BASE_URL=https://your-domain npx playwright test` (use a throwaway deployment: the tests register accounts).

## What I need from you

Choosing a host creates accounts and may involve a payment card for identity checks, so I have not deployed anything. Tell me which path you prefer (or none yet) and I will prepare the exact configuration and walk you through the signup steps.
