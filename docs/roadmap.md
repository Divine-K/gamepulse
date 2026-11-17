# Roadmap

What is built, what is deliberately left out, and what comes next. GamePulse was built in 13 phases, each implemented, tested, documented and pushed before the next began.

## What is built

| Phase | Delivered |
|---|---|
| 1. Setup | Toolchain, repository, PostgreSQL and Redis in Docker Compose |
| 2. Design | Architecture, ER diagram and API conventions, with decision records |
| 3. Backend foundation | FastAPI app factory, async SQLAlchemy, Alembic, structured logs, error envelope, health probes |
| 4. Auth and games | Argon2id and JWT for developers, hashed rotatable API keys for games, tenant isolation tests |
| 5. Players and sessions | Idempotent registration, session lifecycle with heartbeats, automatic abandonment, row locking |
| 6. Scores, leaderboards, achievements | Score ledger, metric-based rankings, configurable achievement engine |
| 7. Real time | Redis pub/sub hub, per-game WebSockets, active-player tracking, cached leaderboards |
| Events and analytics | Transactional event log, validated custom events, engagement, retention and score analytics |
| 8. Frontend foundation | Design tokens, UI kit, routing, auth, API client, WebSocket client |
| 9. Dashboard | Overview, players, sessions, leaderboards, achievements, analytics and live events |
| 10. Developer tools | Live event simulator and an API playground that sends real requests |
| 11. Quality | 21 end-to-end tests, accessibility checks, security review, load and scale test |
| 12. Delivery | Production Docker images, CI on GitHub Actions, free-tier deployment guides |
| 13. Presentation | README, getting started, integration guide, screenshots, example game, this roadmap |

Test counts and performance numbers are in [testing](testing.md); the security review is in [security](security.md).

## Known limits

These are choices and gaps, not surprises. Each is something a production product would want to address.

- **Accounts are minimal.** There is no password reset or email verification, and no teams: a game has exactly one owner. Registration is open.
- **No in-app documentation page yet.** The sidebar item is marked "Soon". The guides in `docs/` cover it for now.
- **No export or alerts.** Analytics cannot be downloaded as CSV or PDF, and nothing sends email or webhook alerts.
- **Rate limiting is a fixed window.** A client can send a burst at a window boundary. Remaining-quota headers (`X-RateLimit-*`) are not sent; a `429` carries `Retry-After`.
- **Free-tier hosting trade-offs.** The deployed API sleeps when idle (about a minute to wake), the database has no scheduled backups, and Redis data is lost on restart. Nothing is lost that cannot be rebuilt (see [architecture](architecture.md)), but a real launch would pay for always-on hosting.
- **Single-machine load test.** The numbers in [testing](testing.md) are a smoke test of one laptop, not a capacity plan.
- **Browser coverage.** The end-to-end suite runs Chrome only.
- **Analytics are computed on request.** They are fast at the tested scale (about 60,000 events), but a much larger game would need pre-aggregated daily tables.
- **No client SDKs.** The Game API is plain REST. A reference Python client lives in [`examples/surfer`](../examples/surfer); there are no packaged Unity, Godot or JavaScript SDKs.

## Next

Roughly in order of value.

1. **In-app documentation page** with the quickstart and a live "connect your game" checklist that turns green when the first event arrives.
2. **Account hardening:** password reset and email verification (with a free transactional email tier), session management, optional two-factor sign-in.
3. **Team access:** invite collaborators to a game with viewer and editor roles.
4. **Packaged SDKs:** a Python package on PyPI and a small JavaScript client, generated from the OpenAPI schema.
5. **Webhooks and alerts:** push achievements, retention drops or error spikes to Discord, Slack or any URL.
6. **Pre-aggregated analytics** (daily rollups) and data export, for games with millions of events.
7. **Token-bucket rate limiting** with remaining-quota headers.
8. **Multi-browser end-to-end runs** (Firefox and WebKit) in CI.
9. **Always-on hosting** with managed backups, once the project has a reason to leave free tiers.
