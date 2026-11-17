"""Report a real Clash Royale player's recent battles to GamePulse.

Clash Royale's official API is read-only: it serves profiles and battle logs but does not push
events. This bridge reads them and replays each battle through the GamePulse Game API as a session
with a score, a custom event and a result, so the dashboard, leaderboards and analytics fill with
real data.

    export CLASH_ROYALE_TOKEN=...      # developer.clashroyale.com (key is tied to your IP)
    export GAMEPULSE_KEY=gp_...        # a GamePulse API key for one of your games
    python examples/clash_royale/bridge.py --tag '#ABC123' --base-url http://localhost:8000

Safe to re-run: every battle has a stable idempotency key, so a battle already imported is skipped.
Only your own data is recorded: opponents are reduced to their crowns, never their name or tag.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "surfer"))
from gamepulse_client import GamePulse, GamePulseError

CR_BASE = "https://api.clashroyale.com/v1"


class ClashRoyaleError(Exception):
    pass


def cr_get(base: str, token: str, path: str) -> object:
    request = urllib.request.Request(
        f"{base}{path}",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as error:
        detail = {}
        try:
            detail = json.loads(error.read() or b"{}")
        except ValueError:
            pass
        hint = {
            403: "the token is wrong, or this computer's IP address is not on its allowed list "
            "(edit the key at developer.clashroyale.com)",
            404: "no such player tag",
            429: "rate limited, try again in a minute",
        }.get(error.code, "")
        reason = detail.get("reason") or detail.get("message") or ""
        raise ClashRoyaleError(f"{error.code} {reason} {hint}".strip()) from None


def parse_time(value: str) -> datetime:
    """Clash Royale timestamps look like 20260117T160000.000Z."""
    return datetime.strptime(value, "%Y%m%dT%H%M%S.%fZ").replace(tzinfo=UTC)


def describe(battle: dict) -> dict | None:
    """Reduce a battle to what we record. Returns None for battles without a clear result."""
    team = (battle.get("team") or [{}])[0]
    opponent = (battle.get("opponent") or [{}])[0]
    if "crowns" not in team or "crowns" not in opponent:
        return None
    mine, theirs = team["crowns"], opponent["crowns"]
    result = "win" if mine > theirs else "loss" if mine < theirs else "draw"
    return {
        "result": result,
        "crowns_for": mine,
        "crowns_against": theirs,
        "trophy_change": team.get("trophyChange"),
        "type": battle.get("type", "unknown"),
        "mode": (battle.get("gameMode") or {}).get("name", "unknown"),
        "arena": (battle.get("arena") or {}).get("name", "unknown"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tag", required=True, help="player tag, for example '#ABC123'")
    parser.add_argument("--base-url", default=os.getenv("GAMEPULSE_URL", "http://localhost:8000"))
    parser.add_argument("--api-key", default=os.getenv("GAMEPULSE_KEY"))
    parser.add_argument("--cr-token", default=os.getenv("CLASH_ROYALE_TOKEN"))
    parser.add_argument("--cr-base-url", default=CR_BASE)
    args = parser.parse_args()
    if not args.api_key or not args.cr_token:
        parser.error("set GAMEPULSE_KEY and CLASH_ROYALE_TOKEN (or pass --api-key / --cr-token)")

    tag = "#" + args.tag.strip().lstrip("#").upper()
    quoted = urllib.parse.quote(tag, safe="")
    try:
        profile = cr_get(args.cr_base_url, args.cr_token, f"/players/{quoted}")
        battles = cr_get(args.cr_base_url, args.cr_token, f"/players/{quoted}/battlelog")
    except ClashRoyaleError as error:
        print(f"Clash Royale API error: {error}", file=sys.stderr)
        return 1

    api = GamePulse(args.base_url, args.api_key)
    try:
        game = api.whoami()
        api.register_player(
            tag,
            profile.get("name"),
            {
                "level": profile.get("expLevel"),
                "trophies": profile.get("trophies"),
                "best_trophies": profile.get("bestTrophies"),
                "arena": (profile.get("arena") or {}).get("name"),
            },
        )
        print(f"{profile.get('name')} ({tag}) -> game {game['name']!r}")

        imported = skipped = 0
        recent = datetime.now(UTC) - timedelta(days=7)
        for battle in reversed(battles):  # the log is newest first; replay oldest first
            info = describe(battle)
            if info is None or "battleTime" not in battle:
                skipped += 1
                continue
            key = f"cr:{tag}:{battle['battleTime']}"
            session = api.start_session(tag, idempotency_key=f"{key}:session")
            if session["status"] != "active":  # replayed: this battle was imported before
                skipped += 1
                continue
            when = parse_time(battle["battleTime"])
            api.submit_score(tag, info["crowns_for"] * 100, session_id=session["id"])
            api.send_event(
                "custom_battle",
                tag,
                session["id"],
                info,
                occurred_at=when.isoformat().replace("+00:00", "Z") if when > recent else None,
                idempotency_key=f"{key}:event",
            )
            api.end_session(session["id"], score=info["crowns_for"] * 100, result=info["result"])
            imported += 1
            score = f"{info['crowns_for']}-{info['crowns_against']}"
            print(f"  {info['result']:<4} {score} {info['mode']}")
        if profile.get("trophies") is not None:
            # A separate ranking, available as the leaderboard metric category:trophies.
            api.submit_score(tag, profile["trophies"], category="trophies")
        print(
            f"\nImported {imported} battles, skipped {skipped}. Current trophies: "
            f"{profile.get('trophies')}. Open the dashboard to see them."
        )
    except GamePulseError as error:
        print(f"GamePulse error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
