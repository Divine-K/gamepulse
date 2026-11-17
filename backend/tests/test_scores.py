import httpx

from tests.helpers import game_with_key, play, register_player, start_session


async def _submit(client: httpx.AsyncClient, key: dict, **body) -> httpx.Response:
    return await client.post("/api/v1/game/scores", json=body, headers=key)


async def test_live_score_updates_the_session_and_end_uses_it(client: httpx.AsyncClient) -> None:
    _, _, key = await game_with_key(client)
    await register_player(client, key)
    session = (await start_session(client, key)).json()

    first = await _submit(client, key, player_external_id="p1", value=120, session_id=session["id"])
    assert first.status_code == 201 and first.json()["category"] == "score"
    await _submit(client, key, player_external_id="p1", value=450, session_id=session["id"])
    live = (await client.get(f"/api/v1/game/sessions/{session['id']}", headers=key)).json()
    assert live["score"] == 450 and live["status"] == "active"

    # Ending without an explicit score keeps the live score.
    ended = await client.post(f"/api/v1/game/sessions/{session['id']}/end", json={}, headers=key)
    assert ended.json()["score"] == 450
    stats = (await client.get("/api/v1/game/players/p1", headers=key)).json()["stats"]
    assert stats["total_score"] == 450 and stats["best_score"] == 450


async def test_explicit_final_score_overrides_the_live_score(client: httpx.AsyncClient) -> None:
    _, _, key = await game_with_key(client)
    await register_player(client, key)
    session = (await start_session(client, key)).json()
    await _submit(client, key, player_external_id="p1", value=999, session_id=session["id"])
    ended = await client.post(
        f"/api/v1/game/sessions/{session['id']}/end", json={"score": 300}, headers=key
    )
    assert ended.json()["score"] == 300


async def test_other_categories_do_not_touch_the_session_score(client: httpx.AsyncClient) -> None:
    _, _, key = await game_with_key(client)
    await register_player(client, key)
    session = (await start_session(client, key)).json()
    response = await _submit(
        client, key, player_external_id="p1", value=42, category="coins", session_id=session["id"]
    )
    assert response.status_code == 201 and response.json()["category"] == "coins"
    live = (await client.get(f"/api/v1/game/sessions/{session['id']}", headers=key)).json()
    assert live["score"] == 0


async def test_standalone_score_without_a_session(client: httpx.AsyncClient) -> None:
    _, _, key = await game_with_key(client)
    await register_player(client, key)
    response = await _submit(client, key, player_external_id="p1", value=88, category="speed_ms")
    assert response.status_code == 201 and response.json()["session_id"] is None


async def test_score_validation(client: httpx.AsyncClient) -> None:
    _, _, key = await game_with_key(client)
    await register_player(client, key)
    assert (await _submit(client, key, player_external_id="p1", value=-1)).status_code == 422
    bad_cat = await _submit(client, key, player_external_id="p1", value=1, category="Bad Cat!")
    assert bad_cat.status_code == 422 and bad_cat.json()["error"]["code"] == "invalid_category"
    ghost = await _submit(client, key, player_external_id="ghost", value=1)
    assert ghost.status_code == 404 and ghost.json()["error"]["code"] == "player_not_found"


async def test_score_for_wrong_player_or_inactive_session(client: httpx.AsyncClient) -> None:
    _, _, key = await game_with_key(client)
    await register_player(client, key, "p1")
    await register_player(client, key, "p2")
    s1 = (await start_session(client, key, "p1")).json()

    wrong_player = await _submit(client, key, player_external_id="p2", value=5, session_id=s1["id"])
    assert wrong_player.status_code == 404

    await client.post(f"/api/v1/game/sessions/{s1['id']}/end", json={}, headers=key)
    late = await _submit(client, key, player_external_id="p1", value=5, session_id=s1["id"])
    assert late.status_code == 409 and late.json()["error"]["code"] == "session_not_active"


async def test_scores_require_a_key(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/api/v1/game/scores", json={"player_external_id": "p", "value": 1}
    )
    assert response.status_code == 401


async def test_end_writes_a_ledger_entry_that_feeds_the_score_category(
    client: httpx.AsyncClient,
) -> None:
    _, _, key = await game_with_key(client)
    await play(client, key, "p1", 700)
    board = (await client.get("/api/v1/game/leaderboards/category:score", headers=key)).json()
    assert [(e["player"]["external_id"], e["value"]) for e in board["items"]] == [("p1", 700)]
