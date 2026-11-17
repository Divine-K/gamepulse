import httpx


async def test_liveness_returns_ok(client: httpx.AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_readiness_checks_postgres_and_redis(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "checks": {"postgres": "ok", "redis": "ok"}}


async def test_readiness_reports_503_when_dependency_down(
    client: httpx.AsyncClient, monkeypatch
) -> None:
    from app.core import redis as redis_module

    class BrokenRedis:
        async def ping(self) -> bool:
            raise ConnectionError("redis down")

    client._transport.app.dependency_overrides[redis_module.get_redis] = lambda: BrokenRedis()  # type: ignore[attr-defined]
    try:
        response = await client.get("/api/v1/health/ready")
    finally:
        client._transport.app.dependency_overrides.clear()  # type: ignore[attr-defined]
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    assert body["checks"] == {"postgres": "ok", "redis": "fail"}
