import asyncio

import httpx
from sqlalchemy import text

from app.core.database import get_engine, get_session_factory
from app.services.sessions import abandon_stale_sessions
from tests.helpers import game_with_key, register_player, start_session


async def _age_session(session_id: str, minutes: int) -> None:
    """Pretend the session's last heartbeat was `minutes` ago."""
    async with get_engine().begin() as conn:
        await conn.execute(
            text(
                "UPDATE game_sessions SET last_heartbeat_at = now() - make_interval(mins => :m), "
                "started_at = now() - make_interval(mins => :m + 1) WHERE id = :id"
            ),
            {"m": minutes, "id": session_id},
        )


async def test_start_session_requires_existing_player(client: httpx.AsyncClient) -> None:
    _, _, key = await game_with_key(client)
    response = await start_session(client, key, "ghost")
    assert response.status_code == 404 and response.json()["error"]["code"] == "player_not_found"


async def test_start_session(client: httpx.AsyncClient) -> None:
    _, _, key = await game_with_key(client)
    await register_player(client, key, "p1", username="Ada")
    response = await start_session(client, key)
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "active" and body["ended_at"] is None
    assert body["player"]["external_id"] == "p1"
    player = (await client.get("/api/v1/game/players/p1", headers=key)).json()
    assert player["stats"]["total_sessions"] == 1


async def test_idempotency_key_replays_the_same_session(client: httpx.AsyncClient) -> None:
    _, _, key = await game_with_key(client)
    await register_player(client, key)
    first = await start_session(client, key, idempotency_key="req-1")
    replay = await start_session(client, key, idempotency_key="req-1")
    assert (first.status_code, replay.status_code) == (201, 200)
    assert first.json()["id"] == replay.json()["id"]
    stats = (await client.get("/api/v1/game/players/p1", headers=key)).json()["stats"]
    assert stats["total_sessions"] == 1  # the retry did not double count


async def test_idempotency_key_cannot_be_shared_across_players(
    client: httpx.AsyncClient,
) -> None:
    _, _, key = await game_with_key(client)
    await register_player(client, key, "p1")
    await register_player(client, key, "p2")
    await start_session(client, key, "p1", idempotency_key="same")
    clash = await start_session(client, key, "p2", idempotency_key="same")
    assert clash.status_code == 409
    assert clash.json()["error"]["code"] == "idempotency_key_reused"


async def test_second_active_session_is_rejected_with_existing_id(
    client: httpx.AsyncClient,
) -> None:
    _, _, key = await game_with_key(client)
    await register_player(client, key)
    first = (await start_session(client, key, idempotency_key="a")).json()
    second = await start_session(client, key, idempotency_key="b")
    assert second.status_code == 409
    error = second.json()["error"]
    assert error["code"] == "session_already_active"
    assert error["details"][0]["session_id"] == first["id"]


async def test_concurrent_starts_create_exactly_one_session(client: httpx.AsyncClient) -> None:
    _, _, key = await game_with_key(client)
    await register_player(client, key)
    results = await asyncio.gather(
        start_session(client, key, idempotency_key="x"),
        start_session(client, key, idempotency_key="y"),
    )
    assert sorted(r.status_code for r in results) == [201, 409]
    stats = (await client.get("/api/v1/game/players/p1", headers=key)).json()["stats"]
    assert stats["total_sessions"] == 1


async def test_heartbeat_extends_the_session(client: httpx.AsyncClient) -> None:
    _, _, key = await game_with_key(client)
    await register_player(client, key)
    session = (await start_session(client, key)).json()
    await _age_session(session["id"], 5)
    aged = (await client.get(f"/api/v1/game/sessions/{session['id']}", headers=key)).json()
    response = await client.post(f"/api/v1/game/sessions/{session['id']}/heartbeat", headers=key)
    assert response.status_code == 200
    beat = response.json()
    assert beat["status"] == "active"
    assert beat["last_heartbeat_at"] > aged["last_heartbeat_at"]  # moved forward ~5 minutes


async def test_end_session_records_result_and_updates_stats(client: httpx.AsyncClient) -> None:
    _, _, key = await game_with_key(client)
    await register_player(client, key)
    session = (await start_session(client, key)).json()
    ended = await client.post(
        f"/api/v1/game/sessions/{session['id']}/end",
        json={"score": 1500, "result": "win"},
        headers=key,
    )
    assert ended.status_code == 200
    body = ended.json()
    assert body["status"] == "completed" and body["score"] == 1500 and body["result"] == "win"
    assert body["ended_at"] and body["duration_seconds"] >= 0

    stats = (await client.get("/api/v1/game/players/p1", headers=key)).json()["stats"]
    assert stats["total_sessions"] == 1 and stats["completed_sessions"] == 1
    assert stats["total_score"] == 1500 and stats["best_score"] == 1500 and stats["wins"] == 1


async def test_best_score_and_totals_accumulate_over_sessions(client: httpx.AsyncClient) -> None:
    _, _, key = await game_with_key(client)
    await register_player(client, key)
    for score, result in [(100, "loss"), (300, "win"), (200, "win")]:
        session = (await start_session(client, key)).json()
        await client.post(
            f"/api/v1/game/sessions/{session['id']}/end",
            json={"score": score, "result": result},
            headers=key,
        )
    stats = (await client.get("/api/v1/game/players/p1", headers=key)).json()["stats"]
    assert stats["completed_sessions"] == 3 and stats["total_score"] == 600
    assert stats["best_score"] == 300 and stats["wins"] == 2


async def test_ending_twice_is_idempotent(client: httpx.AsyncClient) -> None:
    _, _, key = await game_with_key(client)
    await register_player(client, key)
    session = (await start_session(client, key)).json()
    url = f"/api/v1/game/sessions/{session['id']}/end"
    first = await client.post(url, json={"score": 50, "result": "win"}, headers=key)
    second = await client.post(url, json={"score": 9999, "result": "loss"}, headers=key)
    assert second.status_code == 200
    assert second.json()["score"] == 50  # the original result stands
    stats = (await client.get("/api/v1/game/players/p1", headers=key)).json()["stats"]
    assert stats["completed_sessions"] == 1 and stats["total_score"] == 50
    assert first.json()["id"] == second.json()["id"]


async def test_concurrent_ends_count_once(client: httpx.AsyncClient) -> None:
    _, _, key = await game_with_key(client)
    await register_player(client, key)
    session = (await start_session(client, key)).json()
    url = f"/api/v1/game/sessions/{session['id']}/end"
    results = await asyncio.gather(
        *[client.post(url, json={"score": 100, "result": "win"}, headers=key) for _ in range(5)]
    )
    assert all(r.status_code == 200 for r in results)
    stats = (await client.get("/api/v1/game/players/p1", headers=key)).json()["stats"]
    assert stats["completed_sessions"] == 1 and stats["total_score"] == 100 and stats["wins"] == 1


async def test_invalid_end_payloads_are_rejected(client: httpx.AsyncClient) -> None:
    _, _, key = await game_with_key(client)
    await register_player(client, key)
    session = (await start_session(client, key)).json()
    url = f"/api/v1/game/sessions/{session['id']}/end"
    assert (await client.post(url, json={"score": -5}, headers=key)).status_code == 422
    assert (await client.post(url, json={"result": "cheated"}, headers=key)).status_code == 422


async def test_heartbeat_on_completed_session_is_a_conflict(client: httpx.AsyncClient) -> None:
    _, _, key = await game_with_key(client)
    await register_player(client, key)
    session = (await start_session(client, key)).json()
    await client.post(f"/api/v1/game/sessions/{session['id']}/end", json={}, headers=key)
    response = await client.post(f"/api/v1/game/sessions/{session['id']}/heartbeat", headers=key)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "session_not_active"


async def test_reaper_abandons_stale_sessions_and_they_cannot_be_ended(
    client: httpx.AsyncClient,
) -> None:
    _, _, key = await game_with_key(client)
    await register_player(client, key, "stale")
    await register_player(client, key, "fresh")
    stale = (await start_session(client, key, "stale")).json()
    fresh = (await start_session(client, key, "fresh")).json()
    await _age_session(stale["id"], 30)  # default timeout is 15 minutes

    async with get_session_factory()() as session:
        assert await abandon_stale_sessions(session) == 1

    stale_now = (await client.get(f"/api/v1/game/sessions/{stale['id']}", headers=key)).json()
    fresh_now = (await client.get(f"/api/v1/game/sessions/{fresh['id']}", headers=key)).json()
    assert stale_now["status"] == "abandoned" and stale_now["ended_at"] is not None
    assert stale_now["duration_seconds"] >= 60
    assert fresh_now["status"] == "active"

    end = await client.post(f"/api/v1/game/sessions/{stale['id']}/end", json={}, headers=key)
    assert end.status_code == 409 and end.json()["error"]["code"] == "session_not_active"
    # abandoned sessions don't count as completed
    stats = (await client.get("/api/v1/game/players/stale", headers=key)).json()["stats"]
    assert stats["completed_sessions"] == 0 and stats["total_sessions"] == 1


async def test_starting_a_session_reclaims_a_stale_one(client: httpx.AsyncClient) -> None:
    _, _, key = await game_with_key(client)
    await register_player(client, key)
    crashed = (await start_session(client, key)).json()
    await _age_session(crashed["id"], 60)
    fresh = await start_session(client, key)
    assert fresh.status_code == 201
    old = (await client.get(f"/api/v1/game/sessions/{crashed['id']}", headers=key)).json()
    assert old["status"] == "abandoned"


async def test_session_history_for_player_and_dashboard_filters(client: httpx.AsyncClient) -> None:
    jwt, game, key = await game_with_key(client)
    player = await register_player(client, key)
    for _ in range(2):
        s = (await start_session(client, key)).json()
        await client.post(f"/api/v1/game/sessions/{s['id']}/end", json={"score": 10}, headers=key)
    active = (await start_session(client, key)).json()

    history = (await client.get("/api/v1/game/players/p1/sessions?limit=2", headers=key)).json()
    assert history["total"] == 3 and len(history["items"]) == 2
    assert history["items"][0]["id"] == active["id"]  # newest first

    base = f"/api/v1/games/{game['id']}/sessions"
    assert (await client.get(f"{base}?status=active", headers=jwt)).json()["total"] == 1
    assert (await client.get(f"{base}?status=completed", headers=jwt)).json()["total"] == 2
    assert (await client.get(f"{base}?status=bogus", headers=jwt)).status_code == 422
    by_player = await client.get(f"{base}?player_id={player['id']}", headers=jwt)
    assert by_player.json()["total"] == 3
    detail = await client.get(f"{base}/{active['id']}", headers=jwt)
    assert detail.status_code == 200 and detail.json()["player"]["username"] == "p1"
