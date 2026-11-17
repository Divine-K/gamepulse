"""examples/clash_royale/bridge.py against a fake Clash Royale API and a real GamePulse server."""

import asyncio
import json
import subprocess
import sys
import threading
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import httpx
import pytest

from tests.helpers import game_with_key

BRIDGE = Path(__file__).resolve().parents[2] / "examples" / "clash_royale" / "bridge.py"
pytestmark = pytest.mark.usefixtures("live_server")


def _stamp(minutes_ago: int) -> str:
    when = datetime.now(UTC) - timedelta(minutes=minutes_ago)
    return when.strftime("%Y%m%dT%H%M%S.000Z")


def _battle(minutes_ago: int, mine: int, theirs: int) -> dict:
    return {
        "type": "PvP",
        "battleTime": _stamp(minutes_ago),
        "arena": {"name": "Hog Mountain"},
        "gameMode": {"name": "Ladder"},
        "team": [{"tag": "#ME", "name": "Kai", "crowns": mine, "trophyChange": 30}],
        "opponent": [{"tag": "#RIVAL", "name": "SecretRivalName", "crowns": theirs}],
    }


PROFILE = {
    "tag": "#ABC123",
    "name": "Kai",
    "expLevel": 14,
    "trophies": 6543,
    "bestTrophies": 7000,
    "arena": {"name": "Hog Mountain"},
}
# Newest first, like the real battle log. One entry has no crowns and must be skipped.
LOG = [_battle(10, 3, 1), _battle(20, 0, 2), _battle(30, 2, 2), {"type": "boatBattle"}]
LOG[3]["battleTime"] = _stamp(40)


@pytest.fixture
def fake_clash_royale():
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            if self.headers.get("Authorization") != "Bearer good-token":
                code, body = 403, {"reason": "accessDenied.invalidIp"}
            elif self.path == "/v1/players/%23ABC123":
                code, body = 200, PROFILE
            elif self.path == "/v1/players/%23ABC123/battlelog":
                code, body = 200, LOG
            else:
                code, body = 404, {"reason": "notFound"}
            data = json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}/v1"
    server.shutdown()


def _run(live_server: str, cr_base: str, key: str, token: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            sys.executable,
            str(BRIDGE),
            "--tag",
            "#abc123",
            "--base-url",
            live_server.replace("ws://", "http://"),
            "--cr-base-url",
            cr_base,
        ],
        env={"GAMEPULSE_KEY": key, "CLASH_ROYALE_TOKEN": token},
        capture_output=True,
        text=True,
        timeout=120,
    )


async def test_battles_become_sessions_and_reruns_add_nothing(
    live_server: str, client: httpx.AsyncClient, fake_clash_royale: str
) -> None:
    headers, game, key_headers = await game_with_key(client)
    key = key_headers["X-API-Key"]

    first = await asyncio.to_thread(_run, live_server, fake_clash_royale, key, "good-token")
    assert first.returncode == 0, first.stdout + first.stderr
    assert "Imported 3 battles, skipped 1" in first.stdout

    base = f"/api/v1/games/{game['id']}"
    sessions = (await client.get(f"{base}/sessions", headers=headers)).json()
    assert sessions["total"] == 3
    assert sorted(s["result"] for s in sessions["items"]) == ["draw", "loss", "win"]

    events = (
        await client.get(f"{base}/events", params={"event_type": "custom_battle"}, headers=headers)
    ).json()
    assert events["total"] == 3
    assert "SecretRivalName" not in json.dumps(events)  # opponents are never recorded
    assert "#RIVAL" not in json.dumps(events)

    board = (await client.get(f"{base}/leaderboards/category:trophies", headers=headers)).json()
    assert board["items"][0]["value"] == 6543

    # Running it again must not duplicate a single battle.
    second = await asyncio.to_thread(_run, live_server, fake_clash_royale, key, "good-token")
    assert second.returncode == 0, second.stdout + second.stderr
    assert "Imported 0 battles, skipped 4" in second.stdout
    again = (await client.get(f"{base}/sessions", headers=headers)).json()
    assert again["total"] == 3


async def test_a_rejected_clash_royale_token_gives_a_clear_hint(
    live_server: str, client: httpx.AsyncClient, fake_clash_royale: str
) -> None:
    _, _, key_headers = await game_with_key(client)
    done = await asyncio.to_thread(
        _run, live_server, fake_clash_royale, key_headers["X-API-Key"], "wrong-token"
    )
    assert done.returncode == 1
    assert "Clash Royale API error: 403" in done.stderr
    assert "IP address" in done.stderr
