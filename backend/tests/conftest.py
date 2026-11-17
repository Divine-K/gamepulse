from collections.abc import AsyncIterator

import httpx
import pytest_asyncio

from app.core.database import dispose_engine
from app.core.redis import close_redis
from app.main import create_app


@pytest_asyncio.fixture(scope="session")
async def client() -> AsyncIterator[httpx.AsyncClient]:
    app = create_app()
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
        yield http
    await close_redis()
    await dispose_engine()
