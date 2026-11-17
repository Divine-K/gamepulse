from fastapi import APIRouter, Depends

from app.core.dependencies import CurrentDeveloper, DbSession
from app.core.rate_limit import RateLimiter
from app.schemas.auth import (
    DeveloperOut,
    DeveloperUpdate,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
)
from app.services.auth import AuthService

router = APIRouter(prefix="/api/v1", tags=["auth"])


@router.post(
    "/auth/register",
    response_model=DeveloperOut,
    status_code=201,
    dependencies=[Depends(RateLimiter("register"))],
    summary="Register a developer account",
)
async def register(body: RegisterRequest, db: DbSession) -> DeveloperOut:
    developer = await AuthService(db).register(body.email, body.password, body.display_name)
    return DeveloperOut.model_validate(developer)


@router.post(
    "/auth/login",
    response_model=TokenResponse,
    dependencies=[Depends(RateLimiter("login"))],
    summary="Log in and receive a JWT access token",
)
async def login(body: LoginRequest, db: DbSession) -> TokenResponse:
    return await AuthService(db).login(body.email, body.password)


@router.get("/developers/me", response_model=DeveloperOut, summary="Current developer profile")
async def get_me(developer: CurrentDeveloper) -> DeveloperOut:
    return DeveloperOut.model_validate(developer)


@router.patch("/developers/me", response_model=DeveloperOut, summary="Update profile or password")
async def update_me(
    body: DeveloperUpdate, developer: CurrentDeveloper, db: DbSession
) -> DeveloperOut:
    updated = await AuthService(db).update_profile(developer, body)
    return DeveloperOut.model_validate(updated)
