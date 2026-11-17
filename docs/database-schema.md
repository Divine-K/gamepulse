# Database Schema

PostgreSQL 17. UUID primary keys. All timestamps are `timestamptz` stored in UTC. Migrations are managed by Alembic.

## ER diagram

```mermaid
erDiagram
    developers ||--o{ games : owns
    games ||--o{ api_keys : "authenticated by"
    games ||--o{ players : has
    games ||--o{ game_sessions : has
    games ||--o{ events : receives
    games ||--o{ score_entries : has
    games ||--o{ achievement_definitions : configures
    players ||--|| player_stats : summarized_by
    players ||--o{ game_sessions : plays
    players ||--o{ score_entries : earns
    players ||--o{ player_achievements : unlocks
    game_sessions ||--o{ score_entries : produces
    game_sessions ||--o{ events : emits
    achievement_definitions ||--o{ player_achievements : awarded_as

    developers {
        uuid id PK
        text email UK
        text password_hash
        text display_name
        text role "developer | admin"
        bool is_active
        timestamptz created_at
    }
    games {
        uuid id PK
        uuid developer_id FK
        text name
        text slug "unique per developer"
        text description
        text genre
        timestamptz created_at
        timestamptz deleted_at "soft delete"
    }
    api_keys {
        uuid id PK
        uuid game_id FK
        text name
        text key_prefix UK "lookup, not secret"
        text key_hash "sha256"
        timestamptz created_at
        timestamptz last_used_at
        timestamptz revoked_at
    }
    players {
        uuid id PK
        uuid game_id FK
        text external_id "game's own id, unique per game"
        text username
        jsonb metadata
        bool is_simulated
        timestamptz created_at
        timestamptz last_active_at
    }
    player_stats {
        uuid player_id PK
        uuid game_id
        int total_sessions
        int completed_sessions
        bigint total_score
        int best_score
        int wins
        int total_play_seconds
        int achievements_count
        timestamptz updated_at
    }
    game_sessions {
        uuid id PK
        uuid game_id FK
        uuid player_id FK
        text status "active | completed | abandoned"
        text result "win | loss | draw | null"
        int score
        timestamptz started_at
        timestamptz ended_at
        int duration_seconds
        timestamptz last_heartbeat_at
        text idempotency_key
        bool is_simulated
    }
    score_entries {
        uuid id PK
        uuid game_id FK
        uuid player_id FK
        uuid session_id FK "nullable"
        text category "default: score"
        bigint value
        timestamptz created_at
    }
    events {
        uuid id PK
        uuid game_id FK
        uuid player_id FK "nullable"
        uuid session_id FK "nullable"
        text event_type
        jsonb payload
        timestamptz occurred_at
        timestamptz received_at
        text idempotency_key
        bool is_simulated
    }
    achievement_definitions {
        uuid id PK
        uuid game_id FK
        text key "unique per game"
        text name
        text description
        text condition_type
        bigint threshold
        text icon
        bool is_enabled
        timestamptz created_at
    }
    player_achievements {
        uuid id PK
        uuid game_id FK
        uuid player_id FK
        uuid definition_id FK
        uuid session_id "nullable, trigger"
        timestamptz unlocked_at
    }
```

## Tenant integrity constraints

The ER diagram does not show these. They matter most.

| Constraint | Purpose |
|---|---|
| `players UNIQUE (game_id, id)` | Target for composite foreign keys |
| `players UNIQUE (game_id, external_id)` | A game's own player id is unique inside that game and may repeat across games |
| `game_sessions FOREIGN KEY (game_id, player_id) REFERENCES players (game_id, id)` | A session cannot connect game A to game B's player |
| Same composite FK on `score_entries`, `events`, `player_achievements`, `player_stats` | Same guarantee everywhere |
| `game_sessions UNIQUE (game_id, id)` and composite FK from `score_entries`/`events` to it | Child rows must share the session's game |
| `achievement_definitions UNIQUE (game_id, key)` | Stable per-game achievement keys |
| `player_achievements UNIQUE (player_id, definition_id)` | **Duplicate-award prevention** enforced by the database |
| `events UNIQUE (game_id, idempotency_key) WHERE idempotency_key IS NOT NULL` | Idempotent ingestion |
| `game_sessions UNIQUE (game_id, idempotency_key) WHERE idempotency_key IS NOT NULL` | Idempotent session creation |
| `games UNIQUE (developer_id, slug) WHERE deleted_at IS NULL` | Slugs are unique per developer among live games |
| `api_keys UNIQUE (key_prefix)` | Constant-time lookup of the key's row |
| `CHECK (status IN ('active','completed','abandoned'))` and `CHECK (ended_at IS NULL OR ended_at >= started_at)` | State and time sanity |
| Partial unique index on `game_sessions (game_id, player_id) WHERE status='active'` | One active session per player per game (rule can be relaxed per game later) |

## Session state machine

```mermaid
stateDiagram-v2
    [*] --> active: create
    active --> completed: end (score, result)
    active --> abandoned: no heartbeat for N min (reaper)
    completed --> completed: end again with same key (idempotent no-op)
    completed --> [*]
    abandoned --> [*]
```

Invalid transitions (for example ending an abandoned session) return `409 Conflict`.

## Indexes (initial)

- `players (game_id, last_active_at DESC)`, `players (game_id, username)` for search
- `game_sessions (game_id, status)`, `(game_id, started_at DESC)`, `(player_id, started_at DESC)`
- `events (game_id, occurred_at DESC)`, `(game_id, event_type, occurred_at DESC)`
- `score_entries (game_id, category, value DESC)`
- `player_stats (game_id, total_score DESC)`, `(game_id, best_score DESC)`, `(game_id, wins DESC)`

## Achievement conditions

`condition_type` is an enum evaluated by the `AchievementEngine`:

| Type | Meaning | Example |
|---|---|---|
| `sessions_completed` | `completed_sessions >= threshold` | First Game (1), Dedicated Player (10) |
| `score_reached` | any single session score `>= threshold` | High Scorer |
| `total_play_seconds` | accumulated duration `>= threshold` | Veteran |
| `wins` | `wins >= threshold` | Winner |
| `leaderboard_rank` | current rank `<= threshold` | Champion |

New condition types are added by registering an evaluator function, with no schema change.

## Analytics sources

All metrics are SQL aggregates over the tables above: DAU and MAU from `game_sessions`/`events` distinct players, average duration from completed sessions, retention from first-session cohorts, score distributions via `width_bucket` on `score_entries`, and currently active players from Redis, with a Postgres fallback.

## Deferred (not in the MVP)

`leaderboard_snapshots` (historical rankings; added in Phase 6 if time allows), event table partitioning by month, Postgres RLS, organizations and subscription plans.
