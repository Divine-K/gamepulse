"""The example game in examples/surfer must keep working against the real API."""

import asyncio
import subprocess
import sys
from pathlib import Path

import httpx
import pytest

from tests.helpers import game_with_key

EXAMPLE = Path(__file__).resolve().parents[2] / "examples" / "surfer" / "play.py"

pytestmark = pytest.mark.usefixtures("live_server")


async def test_surfer_example_plays_through_the_game_api(
    live_server: str, client: httpx.AsyncClient
) -> None:
    headers, game, key_headers = await game_with_key(client)
    base_url = live_server.replace("ws://", "http://")

    # The example client is blocking, so run it in a thread: the test server shares this loop.
    done = await asyncio.to_thread(
        subprocess.run,
        [sys.executable, str(EXAMPLE), "--base-url", base_url, "--players", "4", "--seed", "7"],
        env={"GAMEPULSE_KEY": key_headers["X-API-Key"]},
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert done.returncode == 0, done.stdout + done.stderr
    assert "4 players played" in done.stdout

    overview = (
        await client.get(f"/api/v1/games/{game['id']}/analytics/overview", headers=headers)
    ).json()
    assert overview["total_players"] == 4
    assert overview["total_sessions"] >= 4
    assert overview["completed_sessions"] == overview["total_sessions"]
    events = (
        await client.get(
            f"/api/v1/games/{game['id']}/events",
            params={"event_type": "custom_wave_ridden"},
            headers=headers,
        )
    ).json()
    assert events["total"] > 0


async def test_surfer_example_reports_a_bad_key_cleanly(live_server: str) -> None:
    base_url = live_server.replace("ws://", "http://")
    done = await asyncio.to_thread(
        subprocess.run,
        [sys.executable, str(EXAMPLE), "--base-url", base_url, "--players", "1"],
        env={"GAMEPULSE_KEY": "gp_000000000000_" + "0" * 64},
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert done.returncode == 1
    assert "GamePulse error: 401" in done.stderr
