import httpx
from fastapi import FastAPI
from pydantic import BaseModel

from app.core.errors import AppError


def _app(client: httpx.AsyncClient) -> FastAPI:
    return client._transport.app  # type: ignore[attr-defined,return-value]


class _Payload(BaseModel):
    name: str


def _register_test_routes(app: FastAPI) -> None:
    if any(getattr(r, "path", "") == "/_test/boom" for r in app.routes):
        return

    @app.get("/_test/boom")
    async def boom() -> None:
        raise RuntimeError("secret internal detail")

    @app.get("/_test/domain-error")
    async def domain_error() -> None:
        raise AppError("session_already_ended", "Session has already ended.", 409)

    @app.post("/_test/validate")
    async def validate(payload: _Payload) -> dict[str, str]:
        return {"name": payload.name}


async def test_unknown_route_uses_error_envelope(client: httpx.AsyncClient) -> None:
    response = await client.get("/does-not-exist")
    assert response.status_code == 404
    error = response.json()["error"]
    assert error["code"] == "not_found"
    assert error["request_id"] == response.headers["X-Request-ID"]


async def test_app_error_maps_to_status_and_code(client: httpx.AsyncClient) -> None:
    _register_test_routes(_app(client))
    response = await client.get("/_test/domain-error")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "session_already_ended"


async def test_validation_error_lists_fields(client: httpx.AsyncClient) -> None:
    _register_test_routes(_app(client))
    response = await client.post("/_test/validate", json={})
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert error["details"][0]["field"] == "body.name"


async def test_unhandled_exception_hides_internals(client: httpx.AsyncClient) -> None:
    _register_test_routes(_app(client))
    response = await client.get("/_test/boom")
    assert response.status_code == 500
    error = response.json()["error"]
    assert error["code"] == "internal_error"
    assert "secret" not in response.text
    assert error["request_id"]


async def test_request_id_is_echoed_when_safe(client: httpx.AsyncClient) -> None:
    response = await client.get("/health", headers={"X-Request-ID": "abc-123"})
    assert response.headers["X-Request-ID"] == "abc-123"


async def test_unsafe_request_id_is_replaced(client: httpx.AsyncClient) -> None:
    response = await client.get("/health", headers={"X-Request-ID": "bad id\twith spaces"})
    assert response.headers["X-Request-ID"] != "bad id\twith spaces"
    assert len(response.headers["X-Request-ID"]) == 36
