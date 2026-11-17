"""Test harness.

Tests run against a dedicated `<db>_test` PostgreSQL database (dropped, recreated and migrated
with Alembic each session) and Redis DB 15, so they can never touch development data.
"""

import asyncio
import os
import socket
import subprocess
import sys
from collections.abc import AsyncIterator
from pathlib import Path

import psycopg
import pytest
import pytest_asyncio
from sqlalchemy.engine import make_url

from app.core.config import Settings

BACKEND_DIR = Path(__file__).resolve().parents[1]

_dev_settings = Settings()
_test_url = make_url(_dev_settings.database_url)
TEST_DB_NAME = f"{_test_url.database}_test"
os.environ["DATABASE_URL"] = _test_url.set(database=TEST_DB_NAME).render_as_string(
    hide_password=False
)
os.environ["REDIS_URL"] = _dev_settings.redis_url.rsplit("/", 1)[0] + "/15"
os.environ["APP_ENV"] = "test"
os.environ["AUTH_RATE_LIMIT_PER_MINUTE"] = "100000"
os.environ["WS_AUTH_TIMEOUT_SECONDS"] = "1"
os.environ["WS_MAX_CONNECTIONS_PER_GAME"] = "3"

import httpx  # noqa: E402
import uvicorn  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.core.database import dispose_engine, get_engine  # noqa: E402
from app.core.redis import close_redis, get_redis  # noqa: E402
from app.main import create_app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _test_database() -> None:
    assert TEST_DB_NAME.endswith("_test")  # never drop a real database
    admin_url = (
        make_url(os.environ["DATABASE_URL"])
        .set(database="postgres", drivername="postgresql")
        .render_as_string(hide_password=False)
    )
    with psycopg.connect(admin_url, autocommit=True) as conn:
        conn.execute(f'DROP DATABASE IF EXISTS "{TEST_DB_NAME}" WITH (FORCE)')
        conn.execute(f'CREATE DATABASE "{TEST_DB_NAME}"')
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        check=True,
        cwd=BACKEND_DIR,
        env=os.environ.copy(),
        capture_output=True,
    )


@pytest_asyncio.fixture(scope="session")
async def client() -> AsyncIterator[httpx.AsyncClient]:
    app = create_app()
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
        yield http
    await close_redis()
    await dispose_engine()


@pytest_asyncio.fixture(scope="session")
async def live_server(client: httpx.AsyncClient) -> AsyncIterator[str]:
    """A real uvicorn server (own app instance and RealtimeHub) in the test event loop.

    HTTP calls through `client` use a different app instance, so events reach WebSocket
    clients only via Redis pub/sub, exactly like two separate API processes.
    Returns the WebSocket base URL, e.g. ws://127.0.0.1:54321.
    """
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    config = uvicorn.Config(
        create_app(), host="127.0.0.1", port=port, log_config=None, lifespan="on"
    )
    server = uvicorn.Server(config)
    task = asyncio.create_task(server.serve())
    for _ in range(100):
        if server.started:
            break
        await asyncio.sleep(0.05)
    assert server.started, "test server failed to start"
    yield f"ws://127.0.0.1:{port}"
    server.should_exit = True
    await task


@pytest_asyncio.fixture(autouse=True)
async def _clean_state(client: httpx.AsyncClient) -> AsyncIterator[None]:
    yield
    async with get_engine().begin() as conn:
        await conn.execute(text("TRUNCATE developers CASCADE"))
    await get_redis().flushdb()  # safe: tests use Redis DB 15 only
