"""Load and scale check for the GamePulse API.

Run against an isolated stack (it creates its own account and game):

    .venv/bin/python scripts/run_e2e_api.py &      # API on :8100 with a throwaway database
    .venv/bin/python scripts/loadtest.py           # prints a latency/throughput table

Part 1 measures request throughput and latency under concurrency. Part 2 seeds a large dataset
directly in the database and times the analytics queries, which scan the most rows.
"""

import asyncio
import statistics
import sys
import time
import uuid
from collections.abc import Awaitable, Callable
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx  # noqa: E402
import psycopg  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402

from app.core.config import Settings  # noqa: E402

BASE = "http://127.0.0.1:8100"
CONCURRENCY = 20
SEED_PLAYERS, SEED_SESSIONS = 2_000, 20_000


def percentile(values: list[float], p: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(len(ordered) * p))]


async def measure(name: str, total: int, call: Callable[[int], Awaitable[httpx.Response]]) -> dict:
    latencies: list[float] = []
    errors = 0
    sem = asyncio.Semaphore(CONCURRENCY)

    async def one(i: int) -> None:
        nonlocal errors
        async with sem:
            started = time.perf_counter()
            response = await call(i)
            latencies.append((time.perf_counter() - started) * 1000)
            if response.status_code >= 400:
                errors += 1

    wall = time.perf_counter()
    await asyncio.gather(*(one(i) for i in range(total)))
    wall = time.perf_counter() - wall
    return {
        "name": name,
        "n": total,
        "rps": total / wall,
        "p50": statistics.median(latencies),
        "p95": percentile(latencies, 0.95),
        "p99": percentile(latencies, 0.99),
        "errors": errors,
    }


def row(r: dict) -> str:
    return (
        f"{r['name']:<38}{r['n']:>6}{r['rps']:>9.0f}{r['p50']:>9.1f}{r['p95']:>9.1f}"
        f"{r['p99']:>9.1f}{r['errors']:>7}"
    )


async def main() -> None:
    limits = httpx.Limits(max_connections=CONCURRENCY * 2)
    async with httpx.AsyncClient(base_url=BASE, timeout=30, limits=limits) as http:
        email = f"load-{uuid.uuid4().hex[:8]}@example.com"
        await http.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "load-test-pass", "display_name": "Load"},
        )
        token = (
            await http.post(
                "/api/v1/auth/login", json={"email": email, "password": "load-test-pass"}
            )
        ).json()["access_token"]
        jwt = {"Authorization": f"Bearer {token}"}
        game = (await http.post("/api/v1/games", json={"name": "Load Test"}, headers=jwt)).json()
        key = (
            await http.post(
                f"/api/v1/games/{game['id']}/api-keys", json={"name": "load"}, headers=jwt
            )
        ).json()["key"]
        gk = {"X-API-Key": key}
        gid = game["id"]

        print(f"\nPart 1: request throughput, concurrency {CONCURRENCY}\n")
        print(
            f"{'endpoint':<38}{'n':>6}{'req/s':>9}{'p50 ms':>9}{'p95 ms':>9}{'p99 ms':>9}{'errors':>7}"
        )
        results = []
        results.append(await measure("GET /health", 600, lambda i: http.get("/health")))
        results.append(
            await measure(
                "POST /game/players (write)",
                300,
                lambda i: http.post(
                    "/api/v1/game/players", json={"external_id": f"p{i}"}, headers=gk
                ),
            )
        )

        async def session_cycle(i: int) -> httpx.Response:
            started = await http.post(
                "/api/v1/game/sessions", json={"player_external_id": f"p{i}"}, headers=gk
            )
            return await http.post(
                f"/api/v1/game/sessions/{started.json()['id']}/end",
                json={"score": 100 + i, "result": "win"},
                headers=gk,
            )

        results.append(await measure("start + end session (2 writes)", 300, session_cycle))
        results.append(
            await measure(
                "POST /game/events (write)",
                300,
                lambda i: http.post(
                    "/api/v1/game/events",
                    json={"event_type": "custom_tick", "payload": {"i": i}},
                    headers=gk,
                ),
            )
        )
        results.append(
            await measure(
                "GET leaderboard (cached)",
                600,
                lambda i: http.get("/api/v1/game/leaderboards/total_score?limit=50", headers=gk),
            )
        )
        results.append(
            await measure(
                "GET game API /me (auth only)",
                600,
                lambda i: http.get("/api/v1/game/me", headers=gk),
            )
        )
        for r in results:
            print(row(r))

    # ---- Part 2: scale ---------------------------------------------------------------------
    print(
        f"\nPart 2: analytics at scale ({SEED_PLAYERS:,} players, {SEED_SESSIONS:,} sessions, ~{SEED_SESSIONS * 3:,} events)\n"
    )
    url = make_url(Settings().database_url)
    dsn = url.set(database=f"{url.database}_e2e", drivername="postgresql").render_as_string(
        hide_password=False
    )
    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute(
            """
            INSERT INTO players (id, game_id, external_id, username, created_at, last_active_at)
            SELECT gen_random_uuid(), %(g)s, 'seed-' || n, 'Seed ' || n,
                   now() - (random() * interval '30 days'), now()
            FROM generate_series(1, %(p)s) n
            """,
            {"g": gid, "p": SEED_PLAYERS},
        )
        conn.execute(
            "INSERT INTO player_stats (player_id, game_id) SELECT id, game_id FROM players WHERE external_id LIKE 'seed-%'"
        )
        conn.execute(
            """
            WITH s AS (
              SELECT gen_random_uuid() AS id, p.id AS player_id, now() - (random() * interval '30 days') AS started,
                     (random() * 600)::int AS dur, (random() * 3000)::int AS score
              FROM generate_series(1, %(s)s) n
              JOIN LATERAL (SELECT id FROM players WHERE game_id = %(g)s AND external_id LIKE 'seed-%%'
                            OFFSET (n %% %(p)s) LIMIT 1) p ON true
            ), ins AS (
              INSERT INTO game_sessions (id, game_id, player_id, status, score, started_at, ended_at, duration_seconds, last_heartbeat_at)
              SELECT id, %(g)s, player_id, 'completed', score, started, started + dur * interval '1 second', dur, started FROM s
              RETURNING id, player_id, started_at, ended_at, score
            )
            INSERT INTO events (id, game_id, player_id, session_id, event_type, payload, occurred_at)
            SELECT gen_random_uuid(), %(g)s, player_id, id, t.type, '{}'::jsonb, CASE WHEN t.type = 'session_ended' THEN ended_at ELSE started_at END
            FROM ins CROSS JOIN (VALUES ('session_started'), ('score_submitted'), ('session_ended')) AS t(type)
            """,
            {"g": gid, "s": SEED_SESSIONS, "p": SEED_PLAYERS},
        )
        conn.execute("ANALYZE")
        conn.execute(
            "UPDATE player_stats ps SET total_score = x.t, completed_sessions = x.c, best_score = x.b FROM (SELECT player_id, sum(score) t, count(*) c, max(score) b FROM game_sessions GROUP BY 1) x WHERE ps.player_id = x.player_id"
        )

    print(f"{'endpoint':<38}{'first ms':>10}{'median of 5 ms':>16}")
    async with httpx.AsyncClient(base_url=BASE, timeout=60) as http:
        for name, path in [
            ("analytics overview (30 days)", f"/api/v1/games/{gid}/analytics/overview?days=30"),
            ("analytics engagement (90 days)", f"/api/v1/games/{gid}/analytics/engagement?days=90"),
            ("analytics retention", f"/api/v1/games/{gid}/analytics/retention"),
            ("analytics score distribution", f"/api/v1/games/{gid}/analytics/scores"),
            (
                "players list (sorted by score)",
                f"/api/v1/games/{gid}/players?sort=-total_score&limit=20",
            ),
            ("players search", f"/api/v1/games/{gid}/players?q=seed-19&limit=20"),
            (
                "leaderboard total_score (live)",
                f"/api/v1/games/{gid}/leaderboards/total_score?limit=50&q=seed",
            ),
            ("sessions list", f"/api/v1/games/{gid}/sessions?limit=20"),
            ("event log", f"/api/v1/games/{gid}/events?limit=20"),
        ]:
            times = []
            for _ in range(6):
                started = time.perf_counter()
                response = await http.get(path, headers=jwt)
                assert response.status_code == 200, (name, response.text)
                times.append((time.perf_counter() - started) * 1000)
            print(f"{name:<38}{times[0]:>10.1f}{statistics.median(times[1:]):>16.1f}")


asyncio.run(main())
