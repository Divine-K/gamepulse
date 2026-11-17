"""Cross-tenant tests: developer B and game B's key must never reach game A's data."""

import uuid

import httpx
from sqlalchemy import text

from app.core.database import get_engine
from tests.helpers import create_game, create_key, signup


async def _two_tenants(client: httpx.AsyncClient):
    a = await signup(client, "a@example.com", "A")
    b = await signup(client, "b@example.com", "B")
    game_a = await create_game(client, a, "Game A")
    game_b = await create_game(client, b, "Game B")
    key_a = await create_key(client, a, game_a["id"])
    key_b = await create_key(client, b, game_b["id"])
    return a, b, game_a, game_b, key_a, key_b


async def test_developer_cannot_access_another_developers_game(client: httpx.AsyncClient) -> None:
    a, b, game_a, _, key_a, _ = await _two_tenants(client)
    gid, kid = game_a["id"], key_a["id"]

    requests = [
        ("GET", f"/api/v1/games/{gid}", None),
        ("PATCH", f"/api/v1/games/{gid}", {"name": "Hijacked"}),
        ("DELETE", f"/api/v1/games/{gid}", None),
        ("GET", f"/api/v1/games/{gid}/api-keys", None),
        ("POST", f"/api/v1/games/{gid}/api-keys", {"name": "evil"}),
        ("POST", f"/api/v1/games/{gid}/api-keys/{kid}/rotate", None),
        ("DELETE", f"/api/v1/games/{gid}/api-keys/{kid}", None),
    ]
    for method, url, body in requests:
        response = await client.request(method, url, json=body, headers=b)
        assert response.status_code == 404, (method, url, response.status_code)
        assert response.json()["error"]["code"] == "game_not_found"

    # Game A is untouched and A's key still works.
    still = await client.get(f"/api/v1/games/{gid}", headers=a)
    assert still.status_code == 200 and still.json()["name"] == "Game A"
    assert (
        await client.get("/api/v1/game/me", headers={"X-API-Key": key_a["key"]})
    ).status_code == 200


async def test_foreign_game_and_unknown_game_are_indistinguishable(
    client: httpx.AsyncClient,
) -> None:
    _, b, game_a, *_ = await _two_tenants(client)
    foreign = await client.get(f"/api/v1/games/{game_a['id']}", headers=b)
    unknown = await client.get(f"/api/v1/games/{uuid.uuid4()}", headers=b)
    assert foreign.status_code == unknown.status_code == 404
    assert foreign.json()["error"]["code"] == unknown.json()["error"]["code"]


async def test_game_lists_only_contain_own_games(client: httpx.AsyncClient) -> None:
    a, b, game_a, game_b, *_ = await _two_tenants(client)
    ids_a = [g["id"] for g in (await client.get("/api/v1/games", headers=a)).json()["items"]]
    ids_b = [g["id"] for g in (await client.get("/api/v1/games", headers=b)).json()["items"]]
    assert ids_a == [game_a["id"]] and ids_b == [game_b["id"]]


async def test_key_cannot_be_managed_through_a_different_game(client: httpx.AsyncClient) -> None:
    """Developer A owns two games; a key of game 1 must not be reachable via game 2's URL."""
    a = await signup(client, "multi@example.com")
    g1 = await create_game(client, a, "One")
    g2 = await create_game(client, a, "Two")
    key = await create_key(client, a, g1["id"])
    response = await client.delete(f"/api/v1/games/{g2['id']}/api-keys/{key['id']}", headers=a)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "api_key_not_found"


async def test_api_key_resolves_only_its_own_game(client: httpx.AsyncClient) -> None:
    _, _, game_a, game_b, key_a, key_b = await _two_tenants(client)
    me_a = await client.get("/api/v1/game/me", headers={"X-API-Key": key_a["key"]})
    me_b = await client.get("/api/v1/game/me", headers={"X-API-Key": key_b["key"]})
    assert me_a.json()["id"] == game_a["id"]
    assert me_b.json()["id"] == game_b["id"]


async def test_jwt_cannot_be_used_as_api_key_and_vice_versa(client: httpx.AsyncClient) -> None:
    a, _, game_a, _, key_a, _ = await _two_tenants(client)
    token = a["Authorization"].removeprefix("Bearer ")
    assert (await client.get("/api/v1/game/me", headers={"X-API-Key": token})).status_code == 401
    as_bearer = await client.get(
        "/api/v1/games", headers={"Authorization": f"Bearer {key_a['key']}"}
    )
    assert as_bearer.status_code == 401


async def test_admin_endpoint_requires_admin_role(client: httpx.AsyncClient) -> None:
    dev = await signup(client, "plain@example.com")
    assert (await client.get("/api/v1/admin/developers", headers=dev)).status_code == 403
    assert (await client.get("/api/v1/admin/developers")).status_code == 401

    admin = await signup(client, "root@example.com")
    async with get_engine().begin() as conn:
        await conn.execute(
            text("UPDATE developers SET role='admin' WHERE email='root@example.com'")
        )
    # Role is read from the database on every request, so promotion applies to the existing token.
    response = await client.get("/api/v1/admin/developers", headers=admin)
    assert response.status_code == 200
    assert response.json()["total"] == 2


async def test_deactivated_developer_is_locked_out(client: httpx.AsyncClient) -> None:
    headers = await signup(client, "gone@example.com")
    async with get_engine().begin() as conn:
        await conn.execute(text("UPDATE developers SET is_active=false"))
    assert (await client.get("/api/v1/developers/me", headers=headers)).status_code == 401
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "gone@example.com", "password": "correct-horse-battery"},
    )
    assert login.status_code == 401
