# Testing and quality assurance

GamePulse is verified at four levels. All of it runs locally with free tools.

| Level | Tool | What it proves | Run it |
|---|---|---|---|
| Backend unit and integration | Pytest + HTTPX (async), real PostgreSQL and Redis | Every endpoint, auth, tenant isolation, concurrency, real WebSockets, migrations | `cd backend && pytest -q` |
| Frontend unit and component | Vitest + Testing Library | Pages, forms, accessibility semantics, API client, WebSocket client | `cd frontend && npm test` |
| End to end | Playwright (installed Google Chrome) | Real browser against a real, isolated stack | `cd frontend && npm run e2e` |
| Performance and scale | `backend/scripts/loadtest.py` | Throughput, latency and analytics query time at scale | see below |

## Isolation: tests never touch development data

- **Backend tests** drop and recreate `<db>_test` (and migrate it with Alembic) each session and use Redis DB 15. The harness asserts the database name ends with `_test` before dropping anything.
- **End-to-end tests** start their own API on port 8100 against `<db>_e2e` with Redis DB 13, plus the production build of the dashboard on port 5174 (`backend/scripts/run_e2e_api.py`). Each test registers its own throwaway accounts.

## What the end-to-end suite covers (21 tests)

- **Onboarding journey:** register, create a game, create an API key (secret shown once), send real requests with that key, then see the player, session, leaderboard rank, achievement and analytics on the dashboard.
- **Live updates:** an event sent through the game API appears on the Live Events feed over the WebSocket with no refresh.
- **Tenant isolation:** another developer's dashboard, URLs, API routes (including simulator and cleanup) and API keys cannot reach a game. All answer 404.
- **Authentication:** protected-route redirect and return, generic wrong-credential message, validation, duplicate email, logout, forged token, and password change invalidating a copied token.
- **Simulator and playground:** the simulator runs against the real backend and its cleanup deletes only simulated rows; the playground sends real requests and the API key never appears in the page, examples or request preview.
- **Responsive:** every page fits a 390px phone screen without sideways page scrolling, the mobile drawer works, and tables scroll inside their card.
- **Accessibility:** axe-core finds no serious or critical WCAG 2.1 A/AA violations on any page, in dark and light themes.
- **Performance budget:** the first page load stays under 700 kB of JavaScript, and the charting library loads only when a chart page opens.
- **Browser console and network gate:** every test fails automatically if the page logs a console error, throws, or the API returns a 5xx.

## Method: tests are checked by breaking the code

For the security-relevant and concurrency-sensitive code, each test was verified by deliberately breaking the behaviour (removing an ownership check, a tenant filter, a row lock, key redaction, the delete confirmation and so on) and confirming a test fails. Several gaps were found and fixed this way, for example a retention test whose data could not tell a correct day window from a wrong one.

## Findings from this phase and what was done

| Finding | Fix |
|---|---|
| The charting library (about 400 kB) loaded on every page, including login | Removed a manual chunk rule that pulled it into the entry graph; it now loads only on chart pages |
| New sign-ups landed on Overview instead of Games | Remember that registration just happened, so the redirect goes to Games |
| Faint "subtle" text, avatar initials, info/success/danger badges and dimmed disabled cards failed WCAG contrast | Darker tokens in both themes, readable avatar initials, and a "Disabled" badge instead of dimming a whole card |
| Chunked request bodies without a Content-Length bypassed the size limit (surfaced as a 400) | The limit now signals with a `BaseException` so it reaches the middleware and returns 413 |
| A password change did not invalidate tokens already issued | `password_changed_at` on the developer; older tokens are rejected, and the dashboard signs the user out |
| Fixture emails on the reserved `.test` domain were rejected by validation | Not a bug: the validator is correct. Tests use `example.com` addresses |

## Performance results

Measured on a laptop with one API worker, PostgreSQL 17 and Redis 7 in Docker, 20 concurrent clients, zero errors.

| Request | Throughput | p50 | p95 |
|---|---|---|---|
| GET /health | 700 req/s | 21 ms | 66 ms |
| POST /game/players (write) | 325 req/s | 52 ms | 124 ms |
| Start + end a session (two writes, stats, achievements, events) | 96 cycles/s | 198 ms | 292 ms |
| POST /game/events (write) | 347 req/s | 44 ms | 130 ms |
| GET leaderboard (cached) | 618 req/s | 28 ms | 53 ms |
| GET game API /me (auth only) | 406 req/s | 37 ms | 121 ms |

Analytics at scale (2,000 players, 20,000 sessions, about 60,000 events):

| Query | Median |
|---|---|
| Overview (30 days) | 52 ms |
| Engagement (90 days) | 43 ms |
| Retention | 12 ms |
| Score distribution | 15 ms |
| Players list sorted by score | 6 ms |
| Leaderboard (live query) | 4 ms |
| Event log, sessions list | 7 to 10 ms |

List endpoints also have an N+1 guard test: the number of SQL statements per request does not grow with the number of rows.

Reproduce: `cd backend && .venv/bin/python scripts/run_e2e_api.py &` then `.venv/bin/python scripts/loadtest.py`.

## Known limits

- The load test is a single-machine smoke test, not a capacity plan. Real deployments should repeat it against the hosting target.
- Playwright runs Chrome only. Firefox and Safari were not exercised.
