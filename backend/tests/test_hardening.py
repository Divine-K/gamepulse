import httpx
from sqlalchemy import event

from app.core.database import get_engine
from tests.helpers import game_with_key, play, register_player, signup


async def test_security_headers_are_on_every_response(client: httpx.AsyncClient) -> None:
    for path in ("/health", "/api/v1/health/ready", "/nope"):
        response = await client.get(path)
        assert response.headers["X-Content-Type-Options"] == "nosniff", path
        assert response.headers["X-Frame-Options"] == "DENY"
        assert response.headers["Referrer-Policy"] == "no-referrer"
        assert "camera=()" in response.headers["Permissions-Policy"]


async def test_json_api_responses_are_never_cached(client: httpx.AsyncClient) -> None:
    jwt = await signup(client)
    for response in (await client.get("/api/v1/games", headers=jwt), await client.get("/nope")):
        assert response.headers["Cache-Control"] == "no-store"


async def test_oversized_bodies_are_rejected_before_they_are_read(
    client: httpx.AsyncClient,
) -> None:
    _, _, key = await game_with_key(client)
    big = "x" * 1_100_000
    declared = await client.post(
        "/api/v1/game/events", json={"event_type": "custom_x", "payload": {"a": big}}, headers=key
    )
    assert declared.status_code == 413
    error = declared.json()["error"]
    assert error["code"] == "payload_too_large"
    assert declared.headers["X-Content-Type-Options"] == "nosniff"


async def test_chunked_bodies_without_a_length_are_limited_too(client: httpx.AsyncClient) -> None:
    _, _, key = await game_with_key(client)

    async def chunks():
        for _ in range(12):  # 12 x 100 KB, sent chunked, no Content-Length
            yield b"x" * 100_000

    response = await client.post(
        "/api/v1/game/events", content=chunks(), headers={**key, "Content-Type": "application/json"}
    )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "payload_too_large"


async def test_normal_requests_are_unaffected_by_the_size_limit(client: httpx.AsyncClient) -> None:
    _, _, key = await game_with_key(client)
    response = await client.post(
        "/api/v1/game/events",
        json={"event_type": "custom_x", "payload": {"note": "a" * 7000}},
        headers=key,
    )
    assert response.status_code == 201


async def test_secrets_never_appear_in_error_responses(client: httpx.AsyncClient) -> None:
    jwt, game, key = await game_with_key(client)
    secret = key["X-API-Key"]
    token = jwt["Authorization"].split()[1]
    for response in (
        await client.get("/api/v1/game/players/ghost", headers=key),
        await client.post("/api/v1/game/events", json={"event_type": "x"}, headers=key),
        await client.get(f"/api/v1/games/{game['id']}/nope", headers=jwt),
    ):
        assert secret not in response.text and token not in response.text


async def test_sql_metacharacters_are_treated_as_data(client: httpx.AsyncClient) -> None:
    jwt, game, key = await game_with_key(client)
    nasty = "'; DROP TABLE players; --"
    await register_player(client, key, nasty, username="Bobby Tables")
    found = await client.get(f"/api/v1/games/{game['id']}/players?q={nasty}", headers=jwt)
    assert found.status_code == 200 and found.json()["total"] == 1
    board = await client.get(
        "/api/v1/game/leaderboards/total_score?q=%27%20OR%201%3D1%20--", headers=key
    )
    assert board.status_code == 200 and board.json()["total"] == 0
    still = await client.get(f"/api/v1/games/{game['id']}/players", headers=jwt)
    assert still.json()["total"] == 1  # the table is intact


async def _count_statements(client: httpx.AsyncClient, url: str, headers: dict) -> int:
    statements: list[str] = []

    def record(conn, cursor, statement, params, context, executemany) -> None:  # noqa: ANN001
        statements.append(statement)

    engine = get_engine().sync_engine
    event.listen(engine, "before_cursor_execute", record)
    try:
        response = await client.get(url, headers=headers)
        assert response.status_code == 200, response.text
    finally:
        event.remove(engine, "before_cursor_execute", record)
    return len(statements)


async def test_list_endpoints_do_not_run_a_query_per_row(client: httpx.AsyncClient) -> None:
    """N+1 guard: the number of SQL statements must not grow with the number of rows."""
    jwt, game, key = await game_with_key(client)
    gid = game["id"]
    urls = [
        f"/api/v1/games/{gid}/players?limit=50",
        f"/api/v1/games/{gid}/sessions?limit=50",
        f"/api/v1/games/{gid}/leaderboards/total_score?limit=50",
        f"/api/v1/games/{gid}/achievements/unlocks?limit=50",
        f"/api/v1/games/{gid}/events?limit=50",
    ]
    for n in range(3):
        await play(client, key, f"few-{n}", 100 + n, "win")
    small = [await _count_statements(client, url, jwt) for url in urls]

    for n in range(25):
        await play(client, key, f"many-{n}", 200 + n, "win")
    large = [await _count_statements(client, url, jwt) for url in urls]

    assert large == small, dict(zip(urls, zip(small, large, strict=True), strict=True))
