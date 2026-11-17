"""Surfer: a pretend game that plays itself through the GamePulse Game API.

    export GAMEPULSE_KEY=gp_xxxxxxxxxxxx_...        # create one in the dashboard (Game, API keys)
    python examples/surfer/play.py --players 12

Every action is a real API call, so the dashboard fills up exactly as it would for a real game:
players appear, sessions run, scores and events stream in, achievements unlock.
"""

from __future__ import annotations

import argparse
import os
import random
import sys

from gamepulse_client import GamePulse, GamePulseError

NAMES = [
    "Kai", "Maya", "Noa", "Leilani", "Rip", "Coral", "Tide", "Sandy", "Wave", "Marlin",
    "Breaker", "Skye", "Pippa", "Finn", "Jetty", "Dune", "Reef", "Swell", "Nalu", "Pearl",
]  # fmt: skip
WAVES = ["Mavericks", "Pipeline", "Nazare", "Jaws", "Teahupoo"]


def play_round(api: GamePulse, rng: random.Random, external_id: str) -> dict:
    """One surf run: start, ride a few waves, maybe level up, end with a result."""
    session = api.start_session(external_id)
    sid = session["id"]
    score = 0
    for _ in range(rng.randint(2, 5)):
        score += rng.randint(80, 600)
        api.submit_score(external_id, score, session_id=sid)
        if rng.random() < 0.5:
            api.send_event(
                "custom_wave_ridden",
                external_id,
                sid,
                {"wave": rng.choice(WAVES), "points": score},
            )
    if rng.random() < 0.25:
        api.send_event("player_level_up", external_id, sid, {"level": rng.randint(2, 9)})
    result = rng.choices(["win", "loss", "draw"], weights=[5, 3, 1])[0]
    return api.end_session(sid, score=score, result=result)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base-url", default=os.getenv("GAMEPULSE_URL", "http://localhost:8000"))
    parser.add_argument("--api-key", default=os.getenv("GAMEPULSE_KEY"))
    parser.add_argument("--players", type=int, default=8, help="how many surfers to create")
    parser.add_argument("--rounds", type=int, default=3, help="runs per surfer")
    parser.add_argument("--seed", type=int, default=None, help="repeatable randomness")
    args = parser.parse_args()
    if not args.api_key:
        parser.error("set GAMEPULSE_KEY or pass --api-key")

    rng = random.Random(args.seed)
    api = GamePulse(args.base_url, args.api_key)
    try:
        game = api.whoami()
        print(f"Playing {game['name']!r} on {args.base_url}")
        unlocked = 0
        for n in range(args.players):
            external_id = f"surfer-{n + 1:03d}"
            name = f"{NAMES[n % len(NAMES)]}{'' if n < len(NAMES) else n // len(NAMES) + 1}"
            api.register_player(external_id, name, {"board": rng.choice(["short", "long", "fish"])})
            for _ in range(rng.randint(1, args.rounds)):
                ended = play_round(api, rng, external_id)
                unlocked += len(ended.get("unlocked_achievements", []))
            print(f"  {name:<10} done")
        print(f"\n{args.players} players played, {unlocked} achievements unlocked. Top 5:")
        for entry in api.leaderboard("total_score", 5)["items"]:
            print(f"  #{entry['rank']} {entry['player']['username']:<10} {entry['value']:>7}")
    except GamePulseError as error:
        print(f"GamePulse error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
