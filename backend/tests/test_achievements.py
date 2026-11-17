import uuid

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.core.database import get_engine
from tests.helpers import game_with_key, play, register_player, start_session


def _keys(end_response: dict) -> list[str]:
    return sorted(a["key"] for a in end_response["unlocked_achievements"])


async def _defs(client: httpx.AsyncClient, jwt: dict, game_id: str) -> dict[str, dict]:
    response = await client.get(f"/api/v1/games/{game_id}/achievements", headers=jwt)
    assert response.status_code == 200
    return {a["key"]: a for a in response.json()}


async def test_new_games_get_default_achievements(client: httpx.AsyncClient) -> None:
    jwt, game, _ = await game_with_key(client)
    defs = await _defs(client, jwt, game["id"])
    assert set(defs) == {
        "first_game",
        "dedicated_player",
        "high_scorer",
        "veteran",
        "winner",
        "champion",
    }
    assert defs["first_game"]["condition_type"] == "sessions_completed"
    assert defs["high_scorer"]["threshold"] == 1000
    assert defs["champion"]["is_enabled"] is False  # opt-in


async def test_first_game_unlocks_once_and_is_never_awarded_twice(
    client: httpx.AsyncClient,
) -> None:
    jwt, game, key = await game_with_key(client)
    first = await play(client, key, "p1", 10)
    assert _keys(first) == ["first_game"]
    second = await play(client, key, "p1", 10)
    assert _keys(second) == []  # no duplicate award

    unlocks = (await client.get("/api/v1/game/players/p1/achievements", headers=key)).json()
    assert unlocks["total"] == 1 and unlocks["items"][0]["achievement"]["key"] == "first_game"
    stats = (await client.get("/api/v1/game/players/p1", headers=key)).json()["stats"]
    assert stats["achievements_count"] == 1


async def test_score_and_win_thresholds(client: httpx.AsyncClient) -> None:
    _, _, key = await game_with_key(client)
    low = await play(client, key, "p1", 999, "loss")
    assert "high_scorer" not in _keys(low)
    high = await play(client, key, "p1", 1000, "win")
    assert "high_scorer" in _keys(high)

    for _ in range(3):
        await play(client, key, "p1", 1, "win")
    fifth_win = await play(client, key, "p1", 1, "win")  # wins: 1 + 3 + 1 = 5
    assert "winner" in _keys(fifth_win)


async def test_dedicated_player_after_ten_completed_sessions(client: httpx.AsyncClient) -> None:
    _, _, key = await game_with_key(client)
    responses = [await play(client, key, "p1", 1) for _ in range(10)]
    assert "dedicated_player" not in [k for r in responses[:9] for k in _keys(r)]
    assert "dedicated_player" in _keys(responses[9])


async def test_veteran_uses_accumulated_play_time(client: httpx.AsyncClient) -> None:
    _, _, key = await game_with_key(client)
    await register_player(client, key, "p1")
    session = (await start_session(client, key)).json()
    async with get_engine().begin() as conn:  # pretend the session lasted 2 hours
        await conn.execute(
            text("UPDATE game_sessions SET started_at = now() - interval '2 hours' WHERE id=:id"),
            {"id": session["id"]},
        )
    ended = await client.post(f"/api/v1/game/sessions/{session['id']}/end", json={}, headers=key)
    assert "veteran" in _keys(ended.json())


async def test_champion_requires_top_rank_and_is_opt_in(client: httpx.AsyncClient) -> None:
    jwt, game, key = await game_with_key(client)
    defs = await _defs(client, jwt, game["id"])
    enabled = await client.patch(
        f"/api/v1/games/{game['id']}/achievements/{defs['champion']['id']}",
        json={"is_enabled": True},
        headers=jwt,
    )
    assert enabled.status_code == 200 and enabled.json()["is_enabled"] is True

    leader = await play(client, key, "leader", 900)
    assert "champion" in _keys(leader)  # first (and only) player is #1
    runner_up = await play(client, key, "runner_up", 100)
    assert "champion" not in _keys(runner_up)


async def test_custom_achievement_create_edit_disable(client: httpx.AsyncClient) -> None:
    jwt, game, key = await game_with_key(client)
    base = f"/api/v1/games/{game['id']}/achievements"
    created = await client.post(
        base,
        json={
            "key": "big_spender",
            "name": "Big Spender",
            "condition_type": "score_reached",
            "threshold": 5000,
            "icon": "gem",
        },
        headers=jwt,
    )
    assert created.status_code == 201
    achievement = created.json()
    assert achievement["unlock_count"] == 0 and achievement["is_enabled"] is True

    duplicate = await client.post(
        base,
        json={"key": "big_spender", "name": "x", "condition_type": "wins", "threshold": 1},
        headers=jwt,
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "achievement_key_taken"

    # Raise the threshold: a 5000-point score no longer qualifies.
    await client.patch(f"{base}/{achievement['id']}", json={"threshold": 9000}, headers=jwt)
    miss = await play(client, key, "p1", 5000)
    assert "big_spender" not in _keys(miss)
    # Lower it back: the next qualifying session unlocks it.
    await client.patch(f"{base}/{achievement['id']}", json={"threshold": 5000}, headers=jwt)
    hit = await play(client, key, "p1", 5000)
    assert "big_spender" in _keys(hit)

    # Disabled achievements are not awarded and leave the player-facing catalogue.
    await client.patch(f"{base}/{achievement['id']}", json={"is_enabled": False}, headers=jwt)
    catalogue = (await client.get("/api/v1/game/achievements", headers=key)).json()
    assert "big_spender" not in [a["key"] for a in catalogue]
    miss2 = await play(client, key, "p2", 7000)
    assert "big_spender" not in _keys(miss2)


async def test_achievement_validation(client: httpx.AsyncClient) -> None:
    jwt, game, _ = await game_with_key(client)
    base = f"/api/v1/games/{game['id']}/achievements"
    good = {"key": "ok_key", "name": "Ok", "condition_type": "wins", "threshold": 3}
    for override in [
        {"key": "Bad Key!"},
        {"threshold": 0},
        {"condition_type": "teleport"},
        {"name": ""},
    ]:
        response = await client.post(base, json={**good, **override}, headers=jwt)
        assert response.status_code == 422, override
    assert (await client.get(f"{base}/{uuid.uuid4()}", headers=jwt)).status_code == 404


async def test_unlock_statistics_and_feed(client: httpx.AsyncClient) -> None:
    jwt, game, key = await game_with_key(client)
    await play(client, key, "p1", 1)
    await play(client, key, "p2", 1)
    await register_player(client, key, "p3")  # never plays

    defs = await _defs(client, jwt, game["id"])
    first = defs["first_game"]
    assert first["unlock_count"] == 2
    assert first["unlock_rate"] == pytest.approx(2 / 3, abs=0.001)
    assert defs["winner"]["unlock_count"] == 0

    base = f"/api/v1/games/{game['id']}"
    feed = (await client.get(f"{base}/achievements/unlocks", headers=jwt)).json()
    assert feed["total"] == 2
    assert {u["player"]["external_id"] for u in feed["items"]} == {"p1", "p2"}
    filtered = (
        await client.get(f"{base}/achievements/unlocks?achievement_id={first['id']}", headers=jwt)
    ).json()
    assert filtered["total"] == 2

    p1 = (await client.get(f"{base}/players?q=p1", headers=jwt)).json()["items"][0]
    history = (await client.get(f"{base}/players/{p1['id']}/achievements", headers=jwt)).json()
    assert history["total"] == 1


async def test_database_rejects_a_duplicate_award(client: httpx.AsyncClient) -> None:
    """The no-duplicates rule is a database constraint, not just application logic."""
    _, game, key = await game_with_key(client)
    await play(client, key, "p1", 1)
    async with get_engine().connect() as conn:
        row = (
            await conn.execute(
                text("SELECT game_id, player_id, definition_id FROM player_achievements LIMIT 1")
            )
        ).one()
    with pytest.raises(IntegrityError):
        async with get_engine().begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO player_achievements (id, game_id, player_id, definition_id) "
                    "VALUES (:id, :g, :p, :d)"
                ),
                {"id": uuid.uuid4(), "g": row[0], "p": row[1], "d": row[2]},
            )


async def test_achievements_are_scoped_to_their_game(client: httpx.AsyncClient) -> None:
    jwt_a, game_a, key_a = await game_with_key(client, "a@example.com", "Game A")
    jwt_b, game_b, key_b = await game_with_key(client, "b@example.com", "Game B")
    await play(client, key_a, "p1", 5000)

    # Game B's catalogue and unlock feed are independent of game A's activity.
    b_defs = await _defs(client, jwt_b, game_b["id"])
    assert all(d["unlock_count"] == 0 for d in b_defs.values())

    # Developer B cannot read or edit game A's achievements.
    a_defs = await _defs(client, jwt_a, game_a["id"])
    target = a_defs["first_game"]["id"]
    base = f"/api/v1/games/{game_a['id']}/achievements"
    assert (await client.get(base, headers=jwt_b)).status_code == 404
    assert (await client.get(f"{base}/{target}", headers=jwt_b)).status_code == 404
    assert (
        await client.patch(f"{base}/{target}", json={"threshold": 99}, headers=jwt_b)
    ).status_code == 404
    assert (await client.get(f"{base}/unlocks", headers=jwt_b)).status_code == 404

    # Using game A's definition id inside game B's URL also fails.
    cross = await client.get(f"/api/v1/games/{game_b['id']}/achievements/{target}", headers=jwt_b)
    assert cross.status_code == 404
