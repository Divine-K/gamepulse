# Security review

Scope: the FastAPI backend, the React dashboard and their data stores, reviewed in Phase 11. Every control below has a test; "Verified by" names it.

## Controls

| Area | Control | Verified by |
|---|---|---|
| Passwords | Argon2id, 8 to 128 characters, hashing runs off the event loop | `test_security`, `test_auth` |
| Login | Same message and timing for unknown email and wrong password; 10 attempts per minute per IP | `test_auth`, e2e `auth.spec` |
| Sessions | HS256 JWT, 60 minutes, `alg: none`, forged and expired tokens rejected; **a password change invalidates earlier tokens** | `test_security`, `test_auth`, e2e |
| Authorization | Role read from the database on every request; deactivated accounts locked out immediately | `test_tenant_isolation` |
| Tenant isolation | Ownership check on every `/games/{id}` route; foreign and unknown games are both 404; repositories always take `game_id`; composite foreign keys reject cross-game rows even in raw SQL | `test_tenant_isolation`, per-feature isolation tests, e2e `isolation.spec` |
| API keys | 256-bit random, only a SHA-256 hash stored, shown once, constant-time compare, rotate and revoke, deleted games kill their keys | `test_api_keys` |
| Game API abuse | Per-game rate limit (429 with `Retry-After`); idempotency keys; payload size limits | `test_events`, `test_hardening` |
| Request size | Bodies over 1 MB get 413 whether announced or streamed in chunks | `test_hardening` |
| Headers | `X-Content-Type-Options`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, restrictive `Permissions-Policy`; JSON responses are `Cache-Control: no-store` | `test_hardening` |
| Injection | SQLAlchemy parameterized queries only; LIKE wildcards escaped in search; no raw SQL built from input | `test_hardening`, `test_players` |
| XSS | React escapes output; the code base has no `dangerouslySetInnerHTML` or `eval` | grep in review |
| CSRF | Not applicable: authentication is a bearer header, not a cookie | design |
| CORS | Explicit origin allow-list, no credentials | config |
| WebSockets | Token sent as the first message (never in the URL or logs), ownership checked, per-game connection cap, slow consumers dropped | `test_realtime` |
| Secrets | Never logged or echoed in errors; the playground keeps a key in memory only and redacts it everywhere; examples use a placeholder | `test_hardening`, e2e `tools.spec` |
| Simulator | Acts only on simulated players; cleanup deletes only simulated rows of one game | `test_simulator` (mutation-checked) |
| Dependencies | Pinned versions | below |

## Tooling results (free, local)

- `npm audit`: **0 vulnerabilities**.
- `pip-audit -r requirements.txt`: **no known vulnerabilities**.
- `bandit -r app` (medium severity and above): **no issues**.
- `ruff`, `eslint` (with jsx-a11y), `tsc --strict`: clean.

## Accepted risks and limitations

| Item | Why it is accepted | Mitigation / next step |
|---|---|---|
| Registration reports "email already exists" | Standard for developer tools; a friendlier flow beats hiding it | Registration is rate limited per IP |
| JWT is kept in `sessionStorage` | Survives refresh but not a closed tab; avoids cookie/CSRF complexity | No unsafe HTML sinks; serve the dashboard with a strict Content-Security-Policy (Phase 12) |
| No refresh tokens or revocation list | Keeps the MVP simple; tokens last 60 minutes | A password change already revokes tokens; add a revocation list if sessions need to be killed individually |
| No per-account lockout | An IP rate limit exists; lockout enables denial of service against a victim | Add alerting in production |
| Rate limiting uses `request.client` | Correct only if the proxy forwards the real client IP | Configure trusted proxy headers when deploying (Phase 12) |
| `/openapi.json` is public | Documents an API that is meant to be documented | The interactive docs page is disabled in production |

## Deployment checklist (Phase 12)

1. Serve everything over HTTPS and set HSTS at the edge.
2. Serve the dashboard with a Content-Security-Policy limiting `connect-src` to the API origin, plus the same headers the API sets.
3. Generate a real `SECRET_KEY` (`openssl rand -hex 32`); never reuse the development one.
4. Set `CORS_ORIGINS` to the dashboard origin only; keep `APP_ENV=production`.
5. Configure trusted proxy headers so rate limits see real client IPs.
6. Use a managed PostgreSQL and Redis with backups, and keep both off the public internet.
