"""The Lichess bridge in examples/lichess, run against a fake Lichess and a real GamePulse server."""

import asyncio
import importlib.util
import json
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import httpx
import pytest

from tests.helpers import game_with_key

BRIDGE = Path(__file__).resolve().parents[2] / "examples" / "lichess" / "bridge.py"

START = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
BLACK_QUEEN_TAKEN = "rnb1kbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 2"
THEN_WHITE_ROOK_TAKEN = "rnb1kbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBN1 b KQkq - 0 2"


def load_bridge():
    spec = importlib.util.spec_from_file_location("lichess_bridge", BRIDGE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def player(colour: str, name: str, rating: int, anonymous: bool = False) -> dict:
    entry = {"color": colour, "rating": rating, "seconds": 180}
    if not anonymous:
        entry["user"] = {"name": name, "id": name.lower(), "title": "GM"}
    return entry


class FakeLichess:
    """Serves one TV feed and the game export, like lichess.org does."""

    def __init__(self, anonymous: bool = False) -> None:
        self.anonymous = anonymous
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args) -> None:  # keep test output quiet
                pass

            def do_GET(self) -> None:  # noqa: N802
                if self.path.startswith("/api/tv/") and self.path.endswith("/feed"):
                    events = [
                        {
                            "t": "featured",
                            "d": {
                                "id": "abcd1234",
                                "players": [
                                    player("white", "Magnus", 2850),
                                    player("black", "Hikaru", 2800, outer.anonymous),
                                ],
                                "fen": START,
                            },
                        },
                        {"t": "fen", "d": {"fen": BLACK_QUEEN_TAKEN, "lm": "d1d8"}},
                        {"t": "fen", "d": {"fen": THEN_WHITE_ROOK_TAKEN, "lm": "d8h1"}},
                    ]
                    body = "".join(json.dumps(e) + "\n" for e in events).encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/x-ndjson")
                    self.end_headers()
                    self.wfile.write(body)
                elif self.path.startswith("/game/export/abcd1234"):
                    body = json.dumps(
                        {
                            "id": "abcd1234",
                            "status": "mate",
                            "winner": "white",
                            "speed": "blitz",
                            "opening": {"name": "Italian Game"},
                        }
                    ).encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(body)
                else:
                    self.send_response(404)
                    self.end_headers()

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()


async def run_bridge(live_server: str, key: str, lichess: FakeLichess):
    return await asyncio.to_thread(
        subprocess.run,
        [
            sys.executable,
            str(BRIDGE),
            "--base-url",
            live_server.replace("ws://", "http://"),
            "--lichess-url",
            lichess.url,
            "--channels",
            "blitz",
            "--once",
        ],
        env={"GAMEPULSE_KEY": key},
        capture_output=True,
        text=True,
        timeout=60,
    )


@pytest.fixture
def lichess():
    fake = FakeLichess()
    yield fake
    fake.close()


# --- pure helpers --------------------------------------------------------------------------------


def test_material_counts_pieces_but_not_kings() -> None:
    bridge = load_bridge()
    assert bridge.material(START) == (39, 39)
    assert bridge.material(BLACK_QUEEN_TAKEN) == (39, 30)
    assert bridge.material(THEN_WHITE_ROOK_TAKEN) == (34, 30)
    assert bridge.material("4k3/8/8/8/8/8/8/4K3 w - - 0 1") == (0, 0)
    assert bridge.material("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR[Qq] w KQkq - 0 1") == (
        39,
        39,
    )


def test_outcome_reads_the_winner_or_a_draw() -> None:
    bridge = load_bridge()
    assert bridge.outcome({"status": "mate", "winner": "black"}) == "black"
    assert bridge.outcome({"status": "stalemate"}) == "draw"
    assert bridge.outcome({"status": "draw"}) == "draw"
    assert bridge.outcome({"status": "started"}) is None
    assert bridge.outcome({}) is None


# --- the bridge end to end -----------------------------------------------------------------------


@pytest.mark.usefixtures("live_server")
async def test_bridge_mirrors_a_live_game(
    live_server: str, client: httpx.AsyncClient, lichess: FakeLichess
) -> None:
    headers, game, key_headers = await game_with_key(client)
    done = await run_bridge(live_server, key_headers["X-API-Key"], lichess)
    assert done.returncode == 0, done.stdout + done.stderr
    assert "1 games followed, 1 finished, 2 captures reported" in done.stdout

    base = f"/api/v1/games/{game['id']}"
    sessions = (await client.get(f"{base}/sessions", headers=headers)).json()["items"]
    by_name = {s["player"]["username"]: s for s in sessions}
    assert set(by_name) == {"Magnus", "Hikaru"}
    # Winner white keeps 34 points of material after losing a rook; black lost the queen.
    assert (by_name["Magnus"]["result"], by_name["Magnus"]["score"]) == ("win", 340)
    assert (by_name["Hikaru"]["result"], by_name["Hikaru"]["score"]) == ("loss", 300)
    assert all(s["status"] == "completed" for s in sessions)

    captures = (
        await client.get(f"{base}/events", params={"event_type": "custom_capture"}, headers=headers)
    ).json()
    assert captures["total"] == 2
    assert sorted(e["payload"]["points"] for e in captures["items"]) == [5, 9]

    board = (await client.get(f"{base}/leaderboards/category:rating", headers=headers)).json()
    assert [(e["player"]["username"], e["value"]) for e in board["items"]] == [
        ("Magnus", 2850),
        ("Hikaru", 2800),
    ]


@pytest.mark.usefixtures("live_server")
async def test_bridge_closes_a_session_left_open_by_a_crashed_run(
    live_server: str, client: httpx.AsyncClient, lichess: FakeLichess
) -> None:
    headers, game, key_headers = await game_with_key(client)
    await client.post(
        "/api/v1/game/players", json={"external_id": "lichess:magnus"}, headers=key_headers
    )
    leftover = await client.post(
        "/api/v1/game/sessions", json={"player_external_id": "lichess:magnus"}, headers=key_headers
    )
    assert leftover.status_code == 201

    done = await run_bridge(live_server, key_headers["X-API-Key"], lichess)
    assert done.returncode == 0, done.stdout + done.stderr

    sessions = (await client.get(f"/api/v1/games/{game['id']}/sessions", headers=headers)).json()[
        "items"
    ]
    assert len(sessions) == 3  # the leftover plus one per player
    assert not [s for s in sessions if s["status"] == "active"]


@pytest.mark.usefixtures("live_server")
async def test_bridge_skips_games_with_an_anonymous_player(
    live_server: str, client: httpx.AsyncClient
) -> None:
    headers, game, key_headers = await game_with_key(client)
    fake = FakeLichess(anonymous=True)
    try:
        done = await run_bridge(live_server, key_headers["X-API-Key"], fake)
    finally:
        fake.close()
    assert done.returncode == 0, done.stdout + done.stderr
    assert "1 skipped" in done.stdout
    sessions = (await client.get(f"/api/v1/games/{game['id']}/sessions", headers=headers)).json()
    assert sessions["total"] == 0


async def test_bridge_reports_a_bad_key_cleanly(live_server: str, lichess: FakeLichess) -> None:
    done = await run_bridge(live_server, "gp_000000000000_" + "0" * 64, lichess)
    assert done.returncode == 1
    assert "GamePulse error: 401" in done.stderr
