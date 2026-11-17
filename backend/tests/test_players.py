import httpx

from tests.helpers import game_with_key, register_player


async def test_register_player_creates_profile_with_zero_stats(client: httpx.AsyncClient) -> None:
    _, _, key = await game_with_key(client)
    response = await client.post(
        "/api/v1/game/players",
        json={"external_id": "steam-123", "username": "Ada", "metadata": {"level": 3}},
        headers=key,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["external_id"] == "steam-123" and body["username"] == "Ada"
    assert body["metadata"] == {"level": 3}
    assert body["stats"]["total_sessions"] == 0 and body["stats"]["total_score"] == 0
    assert body["is_simulated"] is False


async def test_register_is_idempotent_and_does_not_overwrite(client: httpx.AsyncClient) -> None:
    _, _, key = await game_with_key(client)
    first = await register_player(client, key, "p1", username="Original")
    again = await client.post(
        "/api/v1/game/players", json={"external_id": "p1", "username": "Changed"}, headers=key
    )
    assert again.status_code == 200
    assert again.json()["id"] == first["id"] and again.json()["username"] == "Original"


async def test_username_defaults_to_external_id(client: httpx.AsyncClient) -> None:
    _, _, key = await game_with_key(client)
    assert (await register_player(client, key, "anon-42"))["username"] == "anon-42"


async def test_player_validation(client: httpx.AsyncClient) -> None:
    _, _, key = await game_with_key(client)
    empty = await client.post("/api/v1/game/players", json={"external_id": ""}, headers=key)
    assert empty.status_code == 422
    huge = await client.post(
        "/api/v1/game/players",
        json={"external_id": "x", "metadata": {"blob": "a" * 5000}},
        headers=key,
    )
    assert huge.status_code == 422


async def test_game_api_requires_a_key(client: httpx.AsyncClient) -> None:
    for method, url in [("POST", "/api/v1/game/players"), ("GET", "/api/v1/game/players/p1")]:
        response = await client.request(method, url, json={"external_id": "p1"})
        assert response.status_code == 401


async def test_get_player_and_unknown_player(client: httpx.AsyncClient) -> None:
    _, _, key = await game_with_key(client)
    created = await register_player(client, key, "p1")
    fetched = await client.get("/api/v1/game/players/p1", headers=key)
    assert fetched.status_code == 200 and fetched.json()["id"] == created["id"]
    missing = await client.get("/api/v1/game/players/nobody", headers=key)
    assert missing.status_code == 404 and missing.json()["error"]["code"] == "player_not_found"


async def test_same_external_id_can_exist_in_two_games(client: httpx.AsyncClient) -> None:
    _, _, key_a = await game_with_key(client, "a@example.com", "Game A")
    _, _, key_b = await game_with_key(client, "b@example.com", "Game B")
    a = await register_player(client, key_a, "shared-id", username="in-A")
    b = await register_player(client, key_b, "shared-id", username="in-B")
    assert a["id"] != b["id"]
    assert (await client.get("/api/v1/game/players/shared-id", headers=key_a)).json()[
        "username"
    ] == "in-A"


async def test_dashboard_lists_searches_sorts_and_paginates(client: httpx.AsyncClient) -> None:
    jwt, game, key = await game_with_key(client)
    for name in ["alice", "bob", "alina", "carol"]:
        await register_player(client, key, f"id-{name}", username=name)
    base = f"/api/v1/games/{game['id']}/players"

    all_players = (await client.get(base, headers=jwt)).json()
    assert all_players["total"] == 4

    found = (await client.get(f"{base}?q=ali", headers=jwt)).json()
    assert sorted(p["username"] for p in found["items"]) == ["alice", "alina"]

    by_name = (await client.get(f"{base}?sort=username", headers=jwt)).json()["items"]
    assert [p["username"] for p in by_name] == ["alice", "alina", "bob", "carol"]
    reverse = (await client.get(f"{base}?sort=-username&limit=2&offset=1", headers=jwt)).json()
    assert [p["username"] for p in reverse["items"]] == ["bob", "alina"]
    assert reverse["total"] == 4

    assert (await client.get(f"{base}?sort=password", headers=jwt)).status_code == 422
    percent = (await client.get(f"{base}?q=%25", headers=jwt)).json()
    assert percent["total"] == 0  # LIKE wildcards in the search are escaped


async def test_dashboard_player_profile(client: httpx.AsyncClient) -> None:
    jwt, game, key = await game_with_key(client)
    player = await register_player(client, key, "p1", username="Ada")
    response = await client.get(f"/api/v1/games/{game['id']}/players/{player['id']}", headers=jwt)
    assert response.status_code == 200 and response.json()["username"] == "Ada"
