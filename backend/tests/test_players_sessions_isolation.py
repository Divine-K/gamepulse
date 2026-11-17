"""Cross-tenant tests for players and sessions."""

import uuid
from dataclasses import dataclass

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.core.database import get_engine
from tests.helpers import game_with_key, register_player, start_session


@dataclass
class Tenants:
    jwt_a: dict
    game_a: dict
    key_a: dict
    jwt_b: dict
    game_b: dict
    key_b: dict
    player_a: dict
    session_a: dict


async def _tenants(client: httpx.AsyncClient) -> Tenants:
    jwt_a, game_a, key_a = await game_with_key(client, "a@example.com", "Game A")
    jwt_b, game_b, key_b = await game_with_key(client, "b@example.com", "Game B")
    player_a = await register_player(client, key_a, "p1", username="a-player")
    session_a = (await start_session(client, key_a, "p1")).json()
    return Tenants(jwt_a, game_a, key_a, jwt_b, game_b, key_b, player_a, session_a)


async def test_game_key_cannot_reach_another_games_players_or_sessions(
    client: httpx.AsyncClient,
) -> None:
    t = await _tenants(client)
    sid = t.session_a["id"]
    requests = [
        ("GET", "/api/v1/game/players/p1", None),
        ("GET", "/api/v1/game/players/p1/sessions", None),
        ("GET", f"/api/v1/game/sessions/{sid}", None),
        ("POST", f"/api/v1/game/sessions/{sid}/heartbeat", None),
        ("POST", f"/api/v1/game/sessions/{sid}/end", {"score": 1}),
        ("POST", "/api/v1/game/sessions", {"player_external_id": "p1"}),
    ]
    for method, url, body in requests:
        response = await client.request(method, url, json=body, headers=t.key_b)
        assert response.status_code == 404, (method, url, response.status_code)

    # Game A's session is untouched.
    untouched = (await client.get(f"/api/v1/game/sessions/{sid}", headers=t.key_a)).json()
    assert untouched["status"] == "active" and untouched["score"] == 0


async def test_dashboard_cannot_reach_another_developers_players_or_sessions(
    client: httpx.AsyncClient,
) -> None:
    t = await _tenants(client)
    base = f"/api/v1/games/{t.game_a['id']}"
    for url in [
        f"{base}/players",
        f"{base}/players/{t.player_a['id']}",
        f"{base}/players/{t.player_a['id']}/sessions",
        f"{base}/sessions",
        f"{base}/sessions/{t.session_a['id']}",
    ]:
        response = await client.get(url, headers=t.jwt_b)
        assert response.status_code == 404, url


async def test_player_of_game_a_is_not_addressable_through_game_b(
    client: httpx.AsyncClient,
) -> None:
    """Developer B owns game B but passes game A's player id inside game B's URL."""
    t = await _tenants(client)
    base = f"/api/v1/games/{t.game_b['id']}"
    assert (
        await client.get(f"{base}/players/{t.player_a['id']}", headers=t.jwt_b)
    ).status_code == 404
    assert (
        await client.get(f"{base}/sessions/{t.session_a['id']}", headers=t.jwt_b)
    ).status_code == 404
    listing = (await client.get(f"{base}/players", headers=t.jwt_b)).json()
    assert listing["total"] == 0


async def test_stats_are_not_shared_between_games_for_the_same_external_id(
    client: httpx.AsyncClient,
) -> None:
    t = await _tenants(client)
    await register_player(client, t.key_b, "p1")  # same external id, other game
    b_session = (await start_session(client, t.key_b, "p1")).json()
    await client.post(
        f"/api/v1/game/sessions/{b_session['id']}/end", json={"score": 77}, headers=t.key_b
    )
    a_stats = (await client.get("/api/v1/game/players/p1", headers=t.key_a)).json()["stats"]
    b_stats = (await client.get("/api/v1/game/players/p1", headers=t.key_b)).json()["stats"]
    assert a_stats["total_score"] == 0 and a_stats["completed_sessions"] == 0
    assert b_stats["total_score"] == 77


async def test_database_rejects_a_session_linking_players_from_another_game(
    client: httpx.AsyncClient,
) -> None:
    """Defense in depth: the composite foreign key blocks cross-game rows even in raw SQL."""
    t = await _tenants(client)
    with pytest.raises(IntegrityError):
        async with get_engine().begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO game_sessions (id, game_id, player_id) "
                    "VALUES (:id, :game_b, :player_a)"
                ),
                {"id": uuid.uuid4(), "game_b": t.game_b["id"], "player_a": t.player_a["id"]},
            )


async def test_database_enforces_one_active_session_per_player(client: httpx.AsyncClient) -> None:
    t = await _tenants(client)  # player p1 already has an active session
    with pytest.raises(IntegrityError):
        async with get_engine().begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO game_sessions (id, game_id, player_id) "
                    "VALUES (:id, :game_a, :player_a)"
                ),
                {"id": uuid.uuid4(), "game_a": t.game_a["id"], "player_a": t.player_a["id"]},
            )
