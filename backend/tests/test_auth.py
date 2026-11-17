import httpx
from fastapi import Depends, FastAPI

from app.core.rate_limit import RateLimiter
from tests.helpers import PASSWORD, signup


async def test_register_returns_profile_without_secrets(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": "New@Example.com", "password": PASSWORD, "display_name": " Ada "},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "new@example.com"  # normalized
    assert body["display_name"] == "Ada"
    assert body["role"] == "developer"
    assert "password" not in response.text and "hash" not in response.text


async def test_duplicate_email_is_rejected_case_insensitively(client: httpx.AsyncClient) -> None:
    await signup(client, "dup@example.com")
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": "DUP@example.com", "password": PASSWORD, "display_name": "X"},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "email_taken"


async def test_weak_password_and_bad_email_fail_validation(client: httpx.AsyncClient) -> None:
    short = await client.post(
        "/api/v1/auth/register",
        json={"email": "a@example.com", "password": "short", "display_name": "A"},
    )
    assert short.status_code == 422
    bad_email = await client.post(
        "/api/v1/auth/register",
        json={"email": "not-an-email", "password": PASSWORD, "display_name": "A"},
    )
    assert bad_email.status_code == 422


async def test_login_and_profile(client: httpx.AsyncClient) -> None:
    headers = await signup(client, "me@example.com", "Me")
    response = await client.get("/api/v1/developers/me", headers=headers)
    assert response.status_code == 200
    assert response.json()["email"] == "me@example.com"


async def test_wrong_password_and_unknown_email_look_identical(client: httpx.AsyncClient) -> None:
    await signup(client, "real@example.com")
    wrong = await client.post(
        "/api/v1/auth/login", json={"email": "real@example.com", "password": "wrong-password"}
    )
    unknown = await client.post(
        "/api/v1/auth/login", json={"email": "ghost@example.com", "password": "wrong-password"}
    )
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json()["error"]["code"] == unknown.json()["error"]["code"] == "invalid_credentials"
    assert wrong.json()["error"]["message"] == unknown.json()["error"]["message"]


async def test_protected_routes_require_a_valid_token(client: httpx.AsyncClient) -> None:
    missing = await client.get("/api/v1/developers/me")
    assert missing.status_code == 401
    assert missing.json()["error"]["code"] == "not_authenticated"
    assert missing.headers["WWW-Authenticate"] == "Bearer"
    garbage = await client.get(
        "/api/v1/developers/me", headers={"Authorization": "Bearer not.a.token"}
    )
    assert garbage.status_code == 401
    assert garbage.json()["error"]["code"] == "invalid_token"


async def test_update_display_name_and_change_password(client: httpx.AsyncClient) -> None:
    headers = await signup(client, "chg@example.com")
    renamed = await client.patch(
        "/api/v1/developers/me", json={"display_name": "Grace"}, headers=headers
    )
    assert renamed.json()["display_name"] == "Grace"

    wrong = await client.patch(
        "/api/v1/developers/me",
        json={"current_password": "nope-nope-nope", "new_password": "brand-new-password"},
        headers=headers,
    )
    assert wrong.status_code == 403

    changed = await client.patch(
        "/api/v1/developers/me",
        json={"current_password": PASSWORD, "new_password": "brand-new-password"},
        headers=headers,
    )
    assert changed.status_code == 200
    old = await client.post(
        "/api/v1/auth/login", json={"email": "chg@example.com", "password": PASSWORD}
    )
    new = await client.post(
        "/api/v1/auth/login", json={"email": "chg@example.com", "password": "brand-new-password"}
    )
    assert old.status_code == 401
    assert new.status_code == 200


async def test_rate_limiter_returns_429_with_retry_after(client: httpx.AsyncClient) -> None:
    app: FastAPI = client._transport.app  # type: ignore[attr-defined]
    app.add_api_route(
        "/_test/limited",
        lambda: {"ok": True},
        dependencies=[Depends(RateLimiter("unit-test", limit=2))],
    )
    statuses = [(await client.get("/_test/limited")).status_code for _ in range(3)]
    assert statuses == [200, 200, 429]
    blocked = await client.get("/_test/limited")
    assert blocked.json()["error"]["code"] == "rate_limited"
    assert int(blocked.headers["Retry-After"]) > 0
