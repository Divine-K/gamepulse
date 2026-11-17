import httpx

from tests.helpers import create_game, signup


async def test_games_require_authentication(client: httpx.AsyncClient) -> None:
    assert (await client.get("/api/v1/games")).status_code == 401
    assert (await client.post("/api/v1/games", json={"name": "X"})).status_code == 401


async def test_create_get_update_game(client: httpx.AsyncClient) -> None:
    headers = await signup(client)
    game = await create_game(client, headers, "Space Runner!")
    assert game["slug"] == "space-runner"

    fetched = await client.get(f"/api/v1/games/{game['id']}", headers=headers)
    assert fetched.status_code == 200 and fetched.json()["name"] == "Space Runner!"

    patched = await client.patch(
        f"/api/v1/games/{game['id']}",
        json={"description": "Endless runner", "genre": "arcade"},
        headers=headers,
    )
    assert patched.status_code == 200
    assert patched.json()["description"] == "Endless runner"
    assert patched.json()["name"] == "Space Runner!"  # untouched fields are preserved


async def test_duplicate_names_get_unique_slugs(client: httpx.AsyncClient) -> None:
    headers = await signup(client)
    first = await create_game(client, headers, "Same Name")
    second = await create_game(client, headers, "Same Name")
    assert (first["slug"], second["slug"]) == ("same-name", "same-name-2")


async def test_game_validation(client: httpx.AsyncClient) -> None:
    headers = await signup(client)
    response = await client.post("/api/v1/games", json={"name": ""}, headers=headers)
    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["field"] == "body.name"


async def test_list_games_is_paginated(client: httpx.AsyncClient) -> None:
    headers = await signup(client)
    for i in range(3):
        await create_game(client, headers, f"Game {i}")
    page = await client.get("/api/v1/games?limit=2&offset=0", headers=headers)
    body = page.json()
    assert (body["total"], body["limit"], body["offset"], len(body["items"])) == (3, 2, 0, 2)
    rest = await client.get("/api/v1/games?limit=2&offset=2", headers=headers)
    assert len(rest.json()["items"]) == 1
    too_big = await client.get("/api/v1/games?limit=1000", headers=headers)
    assert too_big.status_code == 422


async def test_delete_is_soft_and_frees_the_slug(client: httpx.AsyncClient) -> None:
    headers = await signup(client)
    game = await create_game(client, headers, "Doomed")
    deleted = await client.delete(f"/api/v1/games/{game['id']}", headers=headers)
    assert deleted.status_code == 204
    assert (await client.get(f"/api/v1/games/{game['id']}", headers=headers)).status_code == 404
    listing = await client.get("/api/v1/games", headers=headers)
    assert listing.json()["total"] == 0
    reborn = await create_game(client, headers, "Doomed")
    assert reborn["slug"] == "doomed"
    assert reborn["id"] != game["id"]
