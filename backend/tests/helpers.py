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
