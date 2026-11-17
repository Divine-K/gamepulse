"""Spread an existing game's activity over the last N days, for demos and screenshots.

    python scripts/seed_demo.py --game-id <uuid> [--days 14] [--seed 1]

Play the example game first (examples/surfer/play.py): everything it creates is stamped "now",
so charts show a single day and sessions last a blink. This script moves each player's registration
and each session (with its events, scores and unlocks) back in time, keeping every ordering intact
(a session never starts before its player registered), and gives finished sessions a duration of
2 to 25 minutes. The data is still real API output; only its timestamps and
session durations are altered. It edits one game only and refuses to run when APP_ENV=production.
"""

from __future__ import annotations

import argparse
import asyncio
import random
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.core.database import get_engine  # noqa: E402

SHIFT = "make_interval(secs => :s)"


async def main(game_id: uuid.UUID, days: int, seed: int) -> None:
    if get_settings().app_env == "production":
        raise SystemExit("Refusing to rewrite timestamps with APP_ENV=production.")
    rng = random.Random(seed)
    async with get_engine().begin() as conn:
        found = (
            await conn.execute(text("SELECT name FROM games WHERE id = :g"), {"g": game_id})
        ).first()
        if not found:
            raise SystemExit(f"No game {game_id}")
        players = (
            (await conn.execute(text("SELECT id FROM players WHERE game_id = :g"), {"g": game_id}))
            .scalars()
            .all()
        )
        for pid in players:
            joined = rng.uniform(0.5, days) * 86400  # seconds before now
            p = {"g": game_id, "pid": pid, "s": joined}
            await conn.execute(
                text(
                    f"UPDATE players SET created_at = created_at - {SHIFT}, "
                    f"last_active_at = last_active_at - {SHIFT} WHERE game_id = :g AND id = :pid"
                ),
                p,
            )
            await conn.execute(
                text(
                    f"UPDATE events SET occurred_at = occurred_at - {SHIFT}, "
                    f"received_at = received_at - {SHIFT} "
                    "WHERE game_id = :g AND player_id = :pid AND session_id IS NULL"
                ),
                p,
            )
            sessions = (
                (
                    await conn.execute(
                        text(
                            "SELECT id FROM game_sessions WHERE game_id = :g AND player_id = :pid"
                        ),
                        {"g": game_id, "pid": pid},
                    )
                )
                .scalars()
                .all()
            )
            # Spread the sessions between joining and now, oldest first.
            shifts = sorted((rng.uniform(0, joined) for _ in sessions), reverse=True)
            last = shifts[-1] if shifts else joined
            for sid, shift in zip(sessions, shifts, strict=True):
                q = {"g": game_id, "sid": sid, "s": shift, "d": rng.randint(120, 1500)}
                for sql in (
                    f"UPDATE game_sessions SET started_at = started_at - {SHIFT}, "
                    f"ended_at = ended_at - {SHIFT}, last_heartbeat_at = last_heartbeat_at - {SHIFT}"
                    " WHERE game_id = :g AND id = :sid",
                    f"UPDATE events SET occurred_at = occurred_at - {SHIFT}, "
                    f"received_at = received_at - {SHIFT} WHERE game_id = :g AND session_id = :sid",
                    f"UPDATE score_entries SET created_at = created_at - {SHIFT} "
                    "WHERE game_id = :g AND session_id = :sid",
                    # Real play takes minutes; the example game finishes instantly.
                    "UPDATE game_sessions SET duration_seconds = :d, "
                    "ended_at = started_at + make_interval(secs => :d), "
                    "last_heartbeat_at = started_at + make_interval(secs => :d) "
                    "WHERE game_id = :g AND id = :sid AND ended_at IS NOT NULL",
                ):
                    await conn.execute(text(sql), q)
            # Unlocks happen when a session ends: place them at the player's latest session.
            await conn.execute(
                text(
                    f"UPDATE player_achievements SET unlocked_at = unlocked_at - {SHIFT} "
                    "WHERE game_id = :g AND player_id = :pid"
                ),
                {"g": game_id, "pid": pid, "s": last},
            )
    print(f"Spread {len(players)} players of {found[0]!r} over {days} days.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--game-id", type=uuid.UUID, required=True)
    parser.add_argument("--days", type=int, default=14)
    parser.add_argument("--seed", type=int, default=1)
    args = parser.parse_args()
    asyncio.run(main(args.game_id, args.days, args.seed))
