import asyncio
import json
import uuid

import httpx
import pytest
from websockets.asyncio.client import connect

from tests.helpers import game_with_key, play, register_player, signup, sql_all, start_session


def sim(game_id: str, path: str = "") -> str:
    return f"/api/v1/games/{game_id}/simulator{path}"


async def new_player(client: httpx.AsyncClient, jwt: dict, game_id: str, username=None) -> dict:
    response = await client.post(sim(game_id, "/players"), json={"username": username}, headers=jwt)
    assert response.status_code == 201, response.text
    return response.json()


async def summary(client: httpx.AsyncClient, jwt: dict, game_id: str) -> dict:
    return (await client.get(sim(game_id, "/summary"), headers=jwt)).json()


async def test_test_players_are_flagged_and_listed(client: httpx.AsyncClient) -> None:
    jwt, game, _ = await game_with_key(client)
    player = await new_player(client, jwt, game["id"], "Tester")
    assert player["is_simulated"] is True and player["username"] == "Tester"
    assert player["external_id"].startswith("sim_")

    listed = (await client.get(sim(game["id"], "/players"), headers=jwt)).json()
    assert [p["id"] for p in listed["items"]] == [player["id"]]
    assert (await summary(client, jwt, game["id"]))["players"] == 1
    default_name = await new_player(client, jwt, game["id"])
    assert default_name["username"].startswith("Sim ")


async def test_a_full_simulated_session_is_persisted_and_labelled(
    client: httpx.AsyncClient,
) -> None:
    jwt, game, _ = await game_with_key(client)
    gid = game["id"]
    player = await new_player(client, jwt, gid)

    started = await client.post(
        sim(gid, "/sessions"), json={"player_id": player["id"]}, headers=jwt
    )
    assert started.status_code == 201
    session = started.json()
    assert session["is_simulated"] is True and session["player"]["is_simulated"] is True

    score = await client.post(
        sim(gid, f"/sessions/{session['id']}/score"), json={"value": 1500}, headers=jwt
    )
    assert score.status_code == 201 and score.json()["value"] == 1500

    ended = await client.post(
        sim(gid, f"/sessions/{session['id']}/end"), json={"result": "win"}, headers=jwt
    )
    assert ended.status_code == 200
    body = ended.json()
    assert body["status"] == "completed" and body["score"] == 1500  # the live score was kept
    assert {a["key"] for a in body["unlocked_achievements"]} >= {"first_game", "high_scorer"}

    # Everything it wrote is flagged, in PostgreSQL, and visible in the normal APIs.
    flags = await sql_all("SELECT DISTINCT is_simulated FROM events WHERE game_id = :g", g=gid)
    assert flags == [(True,)]
    sessions = (await client.get(f"/api/v1/games/{gid}/sessions", headers=jwt)).json()
    assert sessions["items"][0]["is_simulated"] is True
    stored = await sql_all("SELECT count(*) FROM score_entries WHERE game_id = :g", g=gid)
    assert stored[0][0] >= 2


async def test_simulated_data_can_be_excluded_from_analytics(client: httpx.AsyncClient) -> None:
    jwt, game, key = await game_with_key(client)
    gid = game["id"]
    await play(client, key, "real", 100, "win")
    player = await new_player(client, jwt, gid)
    session = (
        await client.post(sim(gid, "/sessions"), json={"player_id": player["id"]}, headers=jwt)
    ).json()
    await client.post(sim(gid, f"/sessions/{session['id']}/end"), json={"score": 900}, headers=jwt)

    base = f"/api/v1/games/{gid}/analytics/overview"
    both = (await client.get(base, headers=jwt)).json()
    real = (await client.get(f"{base}?include_simulated=false", headers=jwt)).json()
    assert both["total_players"] == 2 and real["total_players"] == 1
    assert both["total_sessions"] == 2 and real["total_sessions"] == 1
    scores = (
        await client.get(
            f"/api/v1/games/{gid}/analytics/scores?include_simulated=false", headers=jwt
        )
    ).json()
    assert scores["max"] == 100


async def test_custom_events_are_labelled_even_without_a_player(client: httpx.AsyncClient) -> None:
    jwt, game, _ = await game_with_key(client)
    gid = game["id"]
    player = await new_player(client, jwt, gid)

    server = await client.post(
        sim(gid, "/events"), json={"event_type": "custom_server_tick"}, headers=jwt
    )
    assert server.status_code == 201
    assert server.json()["is_simulated"] is True and server.json()["player_id"] is None

    level = await client.post(
        sim(gid, "/events"),
        json={"event_type": "player_level_up", "player_id": player["id"], "payload": {"level": 3}},
        headers=jwt,
    )
    assert level.status_code == 201 and level.json()["payload"] == {"level": 3}

    reserved = await client.post(
        sim(gid, "/events"), json={"event_type": "session_started"}, headers=jwt
    )
    assert reserved.status_code == 422 and reserved.json()["error"]["code"] == "reserved_event_type"


async def test_awarding_an_achievement_is_idempotent_and_counted(client: httpx.AsyncClient) -> None:
    jwt, game, _ = await game_with_key(client)
    gid = game["id"]
    player = await new_player(client, jwt, gid)
    defs = (await client.get(f"/api/v1/games/{gid}/achievements", headers=jwt)).json()
    veteran = next(a for a in defs if a["key"] == "veteran")

    first = await client.post(
        sim(gid, f"/players/{player['id']}/achievements"),
        json={"achievement_id": veteran["id"]},
        headers=jwt,
    )
    again = await client.post(
        sim(gid, f"/players/{player['id']}/achievements"),
        json={"achievement_id": veteran["id"]},
        headers=jwt,
    )
    assert first.json() == {"awarded": True, "achievement_key": "veteran"}
    assert again.json()["awarded"] is False  # never a duplicate

    profile = (await client.get(f"/api/v1/games/{gid}/players/{player['id']}", headers=jwt)).json()
    assert profile["stats"]["achievements_count"] == 1
    unlocks = (await client.get(f"/api/v1/games/{gid}/achievements/unlocks", headers=jwt)).json()
    assert unlocks["total"] == 1
    flagged = await sql_all(
        "SELECT is_simulated FROM events WHERE event_type = 'achievement_unlocked'"
    )
    assert flagged == [(True,)]

    missing = await client.post(
        sim(gid, f"/players/{player['id']}/achievements"),
        json={"achievement_id": str(uuid.uuid4())},
        headers=jwt,
    )
    assert missing.status_code == 404


# --- the simulator must never touch real players -------------------------------------------------


async def test_the_simulator_refuses_to_drive_real_players(client: httpx.AsyncClient) -> None:
    jwt, game, key = await game_with_key(client)
    gid = game["id"]
    real = await register_player(client, key, "real-1", username="Real")
    real_session = (await start_session(client, key, "real-1")).json()
    defs = (await client.get(f"/api/v1/games/{gid}/achievements", headers=jwt)).json()

    attempts = [
        ("POST", "/sessions", {"player_id": real["id"]}),
        ("POST", f"/sessions/{real_session['id']}/score", {"value": 5}),
        ("POST", f"/sessions/{real_session['id']}/end", {"score": 5}),
        ("POST", "/events", {"event_type": "custom_x", "player_id": real["id"]}),
        ("POST", "/events", {"event_type": "custom_x", "session_id": real_session["id"]}),
        ("POST", f"/players/{real['id']}/achievements", {"achievement_id": defs[0]["id"]}),
    ]
    for method, path, body in attempts:
        response = await client.request(method, sim(gid, path), json=body, headers=jwt)
        assert response.status_code == 409, (path, response.status_code)
        assert response.json()["error"]["code"] == "not_simulated"

    # The real session is untouched.
    still = (await client.get(f"/api/v1/game/sessions/{real_session['id']}", headers=key)).json()
    assert still["status"] == "active" and still["score"] == 0


async def test_clearing_deletes_only_simulated_rows(client: httpx.AsyncClient) -> None:
    jwt, game, key = await game_with_key(client)
    gid = game["id"]
    await play(client, key, "real-a", 500, "win")
    await play(client, key, "real-b", 300, "loss")

    for _ in range(2):
        player = await new_player(client, jwt, gid)
        session = (
            await client.post(sim(gid, "/sessions"), json={"player_id": player["id"]}, headers=jwt)
        ).json()
        await client.post(
            sim(gid, f"/sessions/{session['id']}/end"), json={"score": 700}, headers=jwt
        )
    await client.post(sim(gid, "/events"), json={"event_type": "custom_x"}, headers=jwt)

    async def real_counts() -> dict:
        rows = await sql_all(
            "SELECT (SELECT count(*) FROM players WHERE game_id=:g AND NOT is_simulated),"
            "(SELECT count(*) FROM game_sessions WHERE game_id=:g AND NOT is_simulated),"
            "(SELECT count(*) FROM events WHERE game_id=:g AND NOT is_simulated),"
            "(SELECT count(*) FROM player_achievements pa JOIN players p ON p.id=pa.player_id "
            " WHERE pa.game_id=:g AND NOT p.is_simulated),"
            "(SELECT count(*) FROM score_entries s JOIN players p ON p.id=s.player_id "
            " WHERE s.game_id=:g AND NOT p.is_simulated)",
            g=gid,
        )
        return dict(
            zip(["players", "sessions", "events", "unlocks", "scores"], rows[0], strict=True)
        )

    before = await real_counts()
    sims = await summary(client, jwt, gid)
    assert sims["players"] == 2 and sims["sessions"] == 2 and sims["events"] > 4

    cleared = await client.delete(sim(gid, "/data"), headers=jwt)
    assert cleared.status_code == 200 and cleared.json()["deleted"] == sims

    assert await real_counts() == before  # real data is exactly as it was
    assert await summary(client, jwt, gid) == {"players": 0, "sessions": 0, "events": 0}
    leftovers = await sql_all(
        "SELECT (SELECT count(*) FROM players WHERE is_simulated),"
        "(SELECT count(*) FROM game_sessions WHERE is_simulated),"
        "(SELECT count(*) FROM events WHERE is_simulated),"
        "(SELECT count(*) FROM score_entries s WHERE NOT EXISTS (SELECT 1 FROM players p WHERE p.id = s.player_id))"
    )
    assert leftovers == [(0, 0, 0, 0)]
    board = (await client.get(f"/api/v1/games/{gid}/leaderboards/total_score", headers=jwt)).json()
    assert {e["player"]["username"] for e in board["items"]} == {"real-a", "real-b"}


async def test_clearing_one_game_leaves_other_games_simulations_alone(
    client: httpx.AsyncClient,
) -> None:
    jwt_a, game_a, _ = await game_with_key(client, "a@example.com", "Game A")
    jwt_b, game_b, _ = await game_with_key(client, "b@example.com", "Game B")
    await new_player(client, jwt_a, game_a["id"])
    await new_player(client, jwt_b, game_b["id"])
    await client.post(sim(game_b["id"], "/events"), json={"event_type": "custom_x"}, headers=jwt_b)
    b_before = await summary(client, jwt_b, game_b["id"])
    assert b_before["players"] == 1 and b_before["events"] == 2

    await client.delete(sim(game_a["id"], "/data"), headers=jwt_a)
    assert await summary(client, jwt_a, game_a["id"]) == {"players": 0, "sessions": 0, "events": 0}
    assert await summary(client, jwt_b, game_b["id"]) == b_before  # players AND events survive


async def test_clearing_removes_active_players_from_live_tracking(
    client: httpx.AsyncClient,
) -> None:
    jwt, game, _ = await game_with_key(client)
    gid = game["id"]
    player = await new_player(client, jwt, gid)
    await client.post(sim(gid, "/sessions"), json={"player_id": player["id"]}, headers=jwt)
    assert (await client.get(f"/api/v1/games/{gid}/live", headers=jwt)).json()[
        "active_players"
    ] == 1
    await client.delete(sim(gid, "/data"), headers=jwt)
    assert (await client.get(f"/api/v1/games/{gid}/live", headers=jwt)).json()[
        "active_players"
    ] == 0


# --- access control ----------------------------------------------------------------------------------


async def test_simulator_is_tenant_scoped_and_requires_login(client: httpx.AsyncClient) -> None:
    jwt_a, game_a, _ = await game_with_key(client, "a@example.com", "Game A")
    jwt_b, game_b, _ = await game_with_key(client, "b@example.com", "Game B")
    player_a = await new_player(client, jwt_a, game_a["id"])
    gid = game_a["id"]

    for method, path, body in [
        ("GET", "/summary", None),
        ("GET", "/players", None),
        ("POST", "/players", {}),
        ("POST", "/sessions", {"player_id": player_a["id"]}),
        ("DELETE", "/data", None),
    ]:
        assert (
            await client.request(method, sim(gid, path), json=body, headers=jwt_b)
        ).status_code == 404
        assert (await client.request(method, sim(gid, path), json=body)).status_code == 401
    assert (await summary(client, jwt_a, gid))["players"] == 1  # untouched by developer B

    # Game A's simulated player cannot be used through game B's URL either.
    cross = await client.post(
        sim(game_b["id"], "/sessions"), json={"player_id": player_a["id"]}, headers=jwt_b
    )
    assert cross.status_code == 404


async def test_simulated_activity_is_labelled_on_the_live_stream(
    live_server: str, client: httpx.AsyncClient
) -> None:
    jwt, game, _ = await game_with_key(client)
    gid = game["id"]
    ws = await connect(f"{live_server}/api/v1/ws/games/{gid}")
    await ws.send(json.dumps({"type": "auth", "token": jwt["Authorization"].split()[1]}))
    assert json.loads(await ws.recv())["type"] == "ready"

    player = await new_player(client, jwt, gid)
    await client.post(sim(gid, "/sessions"), json={"player_id": player["id"]}, headers=jwt)
    received = []
    async with asyncio.timeout(5):
        while len(received) < 2:
            received.append(json.loads(await ws.recv()))
    assert [e["type"] for e in received] == ["player.registered", "session.started"]
    assert all(e["is_simulated"] is True for e in received)
    assert received[1]["data"]["session"]["player"]["is_simulated"] is True
    await ws.close()


_ = (signup, pytest)
