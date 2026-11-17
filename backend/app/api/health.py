import asyncio
from typing import Literal

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.redis import get_redis

router = APIRouter(tags=["health"])

CHECK_TIMEOUT_SECONDS = 2.0


class LiveResponse(BaseModel):
    status: Literal["ok"]


class ReadyResponse(BaseModel):
    status: Literal["ok", "degraded"]
    checks: dict[str, Literal["ok", "fail"]]


@router.get("/health", response_model=LiveResponse, summary="Liveness probe")
async def live() -> LiveResponse:
    """Process is up. Does not touch dependencies (used by container health checks)."""
    return LiveResponse(status="ok")


@router.get(
    "/api/v1/health/ready",
    response_model=ReadyResponse,
    responses={503: {"model": ReadyResponse}},
    summary="Readiness probe",
)
async def ready(
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> ReadyResponse | JSONResponse:
    """Checks PostgreSQL and Redis. Returns 503 if either is unreachable."""

    async def check_db() -> bool:
        await db.execute(text("SELECT 1"))
        return True

    async def check_redis() -> bool:
        return bool(await redis.ping())

    async def run(check) -> Literal["ok", "fail"]:  # noqa: ANN001
        try:
            await asyncio.wait_for(check(), CHECK_TIMEOUT_SECONDS)
            return "ok"
        except Exception:
            return "fail"

    checks = {"postgres": await run(check_db), "redis": await run(check_redis)}
    healthy = all(v == "ok" for v in checks.values())
    body = ReadyResponse(status="ok" if healthy else "degraded", checks=checks)
    if healthy:
        return body
    return JSONResponse(status_code=503, content=body.model_dump())
