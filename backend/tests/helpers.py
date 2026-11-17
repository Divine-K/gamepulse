import httpx

PASSWORD = "correct-horse-battery"


async def signup(
    client: httpx.AsyncClient, email: str = "dev@example.com", name: str = "Dev"
) -> dict[str, str]:
    """Register + log in; return Authorization headers."""
    registered = await client.post(
        "/api/v1/auth/register", json={"email": email, "password": PASSWORD, "display_name": name}
    )
    assert registered.status_code == 201, registered.text
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


async def create_game(
    client: httpx.AsyncClient, headers: dict[str, str], name: str = "Space Runner"
) -> dict:
    response = await client.post("/api/v1/games", json={"name": name}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


async def create_key(
    client: httpx.AsyncClient, headers: dict[str, str], game_id: str, name: str = "Server"
) -> dict:
    response = await client.post(
        f"/api/v1/games/{game_id}/api-keys", json={"name": name}, headers=headers
    )
    assert response.status_code == 201, response.text
    return response.json()


async def game_with_key(
    client: httpx.AsyncClient, email: str = "dev@example.com", game_name: str = "Space Runner"
) -> tuple[dict[str, str], dict, dict[str, str]]:
    """Return (jwt_headers, game, api_key_headers) for a fresh developer and game."""
    jwt_headers = await signup(client, email)
    game = await create_game(client, jwt_headers, game_name)
    key = await create_key(client, jwt_headers, game["id"])
    return jwt_headers, game, {"X-API-Key": key["key"]}


async def register_player(
    client: httpx.AsyncClient, key_headers: dict[str, str], external_id: str = "p1", **extra
) -> dict:
    response = await client.post(
        "/api/v1/game/players", json={"external_id": external_id, **extra}, headers=key_headers
    )
    assert response.status_code in (200, 201), response.text
    return response.json()


async def start_session(
    client: httpx.AsyncClient,
    key_headers: dict[str, str],
    external_id: str = "p1",
    idempotency_key: str | None = None,
) -> httpx.Response:
    headers = dict(key_headers)
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key
    return await client.post(
        "/api/v1/game/sessions", json={"player_external_id": external_id}, headers=headers
    )
