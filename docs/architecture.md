# GamePulse Architecture

## 1. System overview

```mermaid
flowchart LR
    G[External games<br/>Unity / Unreal / web / simulator] -- "REST + X-API-Key" --> API
    D[React dashboard] -- "REST + JWT" --> API
    D <-- "WebSocket (JWT)" --> WS
    subgraph Backend [FastAPI backend]
        API[REST routers /api/v1] --> SVC[Services]
        WS[WebSocket gateway] --> HUB[Realtime hub]
        SVC --> REPO[Repositories]
        SVC --> HUB
    end
    REPO --> PG[(PostgreSQL<br/>durable data)]
    SVC --> RD[(Redis<br/>cache, live sessions,<br/>rate limits, pub/sub)]
    HUB <--> RD
```

**Two callers, two auth schemes, one set of services.**

| Caller | Credential | Resolves to | Routes |
|---|---|---|---|
| Developer (dashboard) | JWT bearer token | `Developer`, then ownership check on `game_id` | `/api/v1/auth`, `/api/v1/developers`, `/api/v1/games/{game_id}/...` |
| Game (server or client) | `X-API-Key` header | `Game` (key identifies the game and its owner) | `/api/v1/game/...` |

Both route groups call the same service layer. The service receives an already-authorized `GameContext(game_id)` and never trusts a `game_id` from a request body.

## 2. How the pieces communicate

```mermaid
sequenceDiagram
    participant Game
    participant API as FastAPI
    participant PG as PostgreSQL
    participant R as Redis
    participant Dash as Dashboard (WebSocket)

    Game->>API: POST /api/v1/game/sessions (X-API-Key, Idempotency-Key)
    API->>R: rate-limit check, idempotency lookup
    API->>PG: INSERT game_sessions (game_id from key)
    API->>R: ZADD active_sessions
    API->>R: PUBLISH game:{id}:events session.started
    R-->>API: message (hub subscriber)
    API-->>Dash: WS push session.started
    API-->>Game: 201 Created
    Game->>API: POST /sessions/{id}/end (score)
    API->>PG: UPDATE session, INSERT score, UPDATE player_stats
    API->>API: AchievementService.evaluate(player)
    API->>PG: INSERT player_achievements (unique, idempotent)
    API->>R: PUBLISH achievement.unlocked, leaderboard.updated
    API-->>Dash: WS push
```

- **PostgreSQL** is the source of truth. All analytics are computed from its rows.
- **Redis** is never the only copy of important data. If Redis is flushed, the system recovers: active sessions are rebuilt from `game_sessions WHERE status='active'`, and caches refill on demand.
- **WebSocket** messages are notifications. The dashboard refetches via REST through TanStack Query after a push, so a missed message cannot corrupt state.

## 3. Backend module design

```mermaid
flowchart TB
    subgraph api [api/ - HTTP and WS adapters]
        auth_r[auth] --- games_r[games] --- players_r[players] --- sessions_r[sessions]
        lb_r[leaderboards] --- ach_r[achievements] --- events_r[events] --- an_r[analytics] --- ws_r[ws]
    end
    subgraph core [core/ - cross-cutting]
        cfg[config] --- sec[security: JWT, hashing, API keys] --- db[database] --- deps[dependencies] --- err[errors] --- log[logging]
    end
    subgraph services [services/ - business rules]
        s1[AuthService] --- s2[GameService] --- s3[PlayerService] --- s4[SessionService]
        s5[LeaderboardService] --- s6[AchievementEngine] --- s7[EventService] --- s8[AnalyticsService]
    end
    subgraph repos [repositories/ - all SQL, always game-scoped]
        r1[...]
    end
    api --> services --> repos --> models[(models/ SQLAlchemy)]
    api --> schemas[schemas/ Pydantic]
    services --> hub[websocket/ hub + Redis pub/sub]
```

Rules:
1. Routers only parse input, call a service, and shape output. No SQL and no business rules.
2. Services own transactions and rules: session state machine, achievement evaluation, idempotency.
3. Repositories take `game_id` as a required argument for every tenant-owned table. There is no "get player by id" without a game.
4. `schemas/` (Pydantic) are the API contract. `models/` (SQLAlchemy) are persistence. They are never the same class.

## 4. Multi-tenancy and data isolation

Four layers, each enforced in the backend:

1. **Authentication resolves the tenant.** An API key maps to exactly one `game_id`. A JWT maps to a `developer_id`, and the `get_owned_game` dependency checks `games.developer_id == developer_id` before any `/games/{game_id}/...` handler runs. A foreign game returns **404**, not 403, so existence isn't leaked.
2. **Repositories require `game_id`.** Every query on a tenant table filters on it.
3. **Composite foreign keys.** For example `game_sessions(game_id, player_id)` references `players(game_id, id)`, so the database rejects a session that links one game's player to another game's session even if application code has a bug.
4. **Tests.** Each endpoint has a cross-tenant test: developer A, game A's key, and developer B must all fail to read or write game B's data.

Postgres Row-Level Security was considered and deferred (see ADR-004).

## 5. Real-time design

- Redis pub/sub channel per game: `gp:game:{game_id}:events`. Services publish JSON envelopes `{type, game_id, data, ts}`.
- The `RealtimeHub` subscribes lazily to a game's channel when its first WebSocket client connects and unsubscribes after the last disconnects. Multiple backend processes work because Redis fans out.
- **Dashboard WebSocket:** `GET /api/v1/ws/games/{game_id}`. The client connects, then sends `{"type":"auth","token":"<jwt>"}` as the first message within 5 seconds. A token in the URL would leak into logs, so none is used. The server verifies ownership and then streams.
- Client reconnect: exponential backoff with jitter, then a REST refetch after reconnect.
- **Active sessions:** Redis sorted set `gp:game:{id}:active` with score = last heartbeat timestamp. A background task marks sessions with no heartbeat for N minutes as `abandoned` (default 15, configurable). "Currently active players" is the count of distinct players in that set.
- Event envelope types: `session.started`, `session.ended`, `score.submitted`, `achievement.unlocked`, `leaderboard.updated`, `event.received`, `player.registered`.

## 6. Frontend architecture

```mermaid
flowchart TB
    main[main.tsx] --> prov[Providers: QueryClient, Auth, Toast, Theme]
    prov --> router[React Router]
    router --> authL[AuthLayout: login / register]
    router --> shell[AppShell: sidebar, topbar, breadcrumbs, game selector]
    shell --> pages[pages: Overview, Games, Players, Sessions, Leaderboards,<br/>Achievements, LiveEvents, Analytics, Playground, Docs, Settings]
    pages --> feat[feature components: charts, tables, forms]
    feat --> ui[components/ui: Button, Card, Modal, Dropdown, Toast, Skeleton, Table, Tabs]
    pages --> hooks[hooks: useGames, usePlayers, useLiveEvents ...]
    hooks --> svc[services: apiClient, wsClient, per-resource API modules]
    svc --> BE[(FastAPI)]
```

- **State:** server state in TanStack Query. Auth and selected game live in React context. No global store.
- **Design tokens** are CSS variables (colour, type, spacing, radius, shadow, motion durations), exposed to Tailwind via `@theme`.
- **Motion** is wrapped in small components (`PageTransition`, `FadeIn`, `Presence`) that respect `prefers-reduced-motion`.
- **Validation:** Zod schemas + React Hook Form; API response types in `types/`.

## 7. Architecture Decision Records

| # | Decision | Rationale | Trade-off |
|---|---|---|---|
| ADR-001 | **Async stack**: async SQLAlchemy 2 + psycopg 3 + `redis.asyncio` | WebSockets and Redis pub/sub are natively async; one concurrency model | Slightly harder tests (pytest-asyncio) |
| ADR-002 | **Layered architecture** (api → services → repositories) | Testable rules, no SQL in routers, isolation enforced in one place | More files than a flat app |
| ADR-003 | **API keys stored as SHA-256 hashes**, format `gp_<prefix>_<secret>`; prefix indexed for lookup | Keys are 256-bit random, so a fast hash is safe and cheap per request (Argon2 is for low-entropy passwords) | Secret shown once; lost key means rotate |
| ADR-004 | **App-level tenant isolation + composite FKs**, no Postgres RLS in the MVP | Simple, visible in code, testable. RLS needs per-request session variables and complicates pooling | Relies on discipline and tests; RLS is a future hardening |
| ADR-005 | **Passwords with Argon2id** (pwdlib) | Current best practice | Slower login by design |
| ADR-006 | **JWT access tokens only** (60 min, HS256) | Enough for MVP. Refresh-token rotation is future work | Re-login after expiry |
| ADR-007 | **Idempotency via `Idempotency-Key` header** (unique per game) for session start and event ingestion | Games retry on flaky networks | Keys stored in a unique column |
| ADR-008 | **Denormalized `player_stats` row** updated in the same transaction as session end | O(1) leaderboard reads; avoids aggregating millions of rows | Must stay consistent; covered by tests |
| ADR-009 | **Leaderboards are metric-based** (`total_score`, `best_score`, `wins`, `achievements`), with a `category` on score entries | New ranking categories need no schema change | Rank computed with window functions + Redis cache |
| ADR-010 | **Events stored as JSONB payload + indexed type/time** | Custom event types without migrations | Payload validated per known type, free-form for `custom_*` |
| ADR-011 | **UUID primary keys** | Safe to expose, no enumeration | Larger indexes |
| ADR-012 | **`is_simulated` flag** on players, sessions and events | Simulator data is clearly labelled and can be cleaned without touching real data | One more column |
| ADR-013 | **Zero-cost constraint**: only open-source libraries and free tiers; no paid APIs, no paid LLM or AI calls inside the app | Personal portfolio project with no budget | Free hosting tiers sleep, are rate-limited, and may require a card for identity verification, so we check this before choosing a host in Phase 12 |
