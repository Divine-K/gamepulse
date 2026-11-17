import httpx

from tests.helpers import create_game, create_key, signup


async def test_create_key_shows_secret_once_and_authenticates(client: httpx.AsyncClient) -> None:
    headers = await signup(client)
    game = await create_game(client, headers)
    created = await create_key(client, headers, game["id"])
    secret = created["key"]
    assert secret.startswith(f"gp_{created['key_prefix']}_")

    listing = await client.get(f"/api/v1/games/{game['id']}/api-keys", headers=headers)
    assert listing.status_code == 200
    assert secret not in listing.text and "key_hash" not in listing.text
    assert listing.json()[0]["key_prefix"] == created["key_prefix"]

    me = await client.get("/api/v1/game/me", headers={"X-API-Key": secret})
    assert me.status_code == 200
    assert me.json()["id"] == game["id"]

    listing = await client.get(f"/api/v1/games/{game['id']}/api-keys", headers=headers)
    assert listing.json()[0]["last_used_at"] is not None


async def test_stored_key_is_hashed(client: httpx.AsyncClient) -> None:
    from sqlalchemy import text

    from app.core.database import get_engine

    headers = await signup(client)
    game = await create_game(client, headers)
    created = await create_key(client, headers, game["id"])
    async with get_engine().connect() as conn:
        stored = (await conn.execute(text("SELECT key_hash FROM api_keys"))).scalar_one()
    assert stored != created["key"] and created["key"] not in stored
    assert len(stored) == 64


async def test_missing_or_malformed_api_key_is_rejected(client: httpx.AsyncClient) -> None:
    for headers in ({}, {"X-API-Key": "garbage"}, {"X-API-Key": "gp_" + "a" * 12 + "_" + "b" * 64}):
        response = await client.get("/api/v1/game/me", headers=headers)
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "invalid_api_key"


async def test_key_with_right_prefix_but_wrong_secret_is_rejected(
    client: httpx.AsyncClient,
) -> None:
    headers = await signup(client)
    game = await create_game(client, headers)
    created = await create_key(client, headers, game["id"])
    forged = f"gp_{created['key_prefix']}_{'0' * 64}"
    response = await client.get("/api/v1/game/me", headers={"X-API-Key": forged})
    assert response.status_code == 401


async def test_rotate_revokes_old_key_and_issues_new(client: httpx.AsyncClient) -> None:
    headers = await signup(client)
    game = await create_game(client, headers)
    old = await create_key(client, headers, game["id"], "Prod")
    rotated = await client.post(
        f"/api/v1/games/{game['id']}/api-keys/{old['id']}/rotate", headers=headers
    )
    assert rotated.status_code == 201
    new = rotated.json()
    assert new["name"] == "Prod" and new["key"] != old["key"]
    assert (
        await client.get("/api/v1/game/me", headers={"X-API-Key": old["key"]})
    ).status_code == 401
    assert (
        await client.get("/api/v1/game/me", headers={"X-API-Key": new["key"]})
    ).status_code == 200

    again = await client.post(
        f"/api/v1/games/{game['id']}/api-keys/{old['id']}/rotate", headers=headers
    )
    assert again.status_code == 409 and again.json()["error"]["code"] == "key_revoked"


async def test_revoke_key_is_idempotent(client: httpx.AsyncClient) -> None:
    headers = await signup(client)
    game = await create_game(client, headers)
    key = await create_key(client, headers, game["id"])
    url = f"/api/v1/games/{game['id']}/api-keys/{key['id']}"
    assert (await client.delete(url, headers=headers)).status_code == 204
    assert (await client.delete(url, headers=headers)).status_code == 204
    assert (
        await client.get("/api/v1/game/me", headers={"X-API-Key": key["key"]})
    ).status_code == 401
    listing = await client.get(f"/api/v1/games/{game['id']}/api-keys", headers=headers)
    assert listing.json()[0]["revoked_at"] is not None


async def test_deleting_a_game_kills_its_keys(client: httpx.AsyncClient) -> None:
    headers = await signup(client)
    game = await create_game(client, headers)
    key = await create_key(client, headers, game["id"])
    await client.delete(f"/api/v1/games/{game['id']}", headers=headers)
    response = await client.get("/api/v1/game/me", headers={"X-API-Key": key["key"]})
    assert response.status_code == 401
