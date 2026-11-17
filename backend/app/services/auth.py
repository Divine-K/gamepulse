import asyncio
from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.security import (
    DUMMY_PASSWORD_HASH,
    create_access_token,
    hash_password,
    verify_password,
)
from app.models import Developer
from app.repositories.developers import DeveloperRepository
from app.schemas.auth import DeveloperUpdate, TokenResponse


def _email_taken() -> AppError:
    return AppError("email_taken", "An account with this email already exists.", 409)


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.developers = DeveloperRepository(session)

    async def register(self, email: str, password: str, display_name: str) -> Developer:
        email = email.strip().lower()
        if await self.developers.get_by_email(email):
            raise _email_taken()
        # Argon2 is CPU-heavy: keep it off the event loop.
        password_hash = await asyncio.to_thread(hash_password, password)
        developer = Developer(email=email, password_hash=password_hash, display_name=display_name)
        self.developers.add(developer)
        try:
            await self.session.commit()
        except IntegrityError:  # lost a race with a concurrent registration
            await self.session.rollback()
            raise _email_taken() from None
        return developer

    async def login(self, email: str, password: str) -> TokenResponse:
        developer = await self.developers.get_by_email(email.strip().lower())
        stored_hash = developer.password_hash if developer else DUMMY_PASSWORD_HASH
        password_ok = await asyncio.to_thread(verify_password, password, stored_hash)
        if developer is None or not password_ok or not developer.is_active:
            raise AppError("invalid_credentials", "Incorrect email or password.", 401)
        token, expires_in = create_access_token(str(developer.id), developer.role)
        return TokenResponse(access_token=token, expires_in=expires_in)

    async def update_profile(self, developer: Developer, data: DeveloperUpdate) -> Developer:
        if data.display_name is not None:
            developer.display_name = data.display_name.strip() or developer.display_name
        if data.new_password is not None:
            if not data.current_password:
                raise AppError("current_password_required", "Current password is required.", 422)
            valid = await asyncio.to_thread(
                verify_password, data.current_password, developer.password_hash
            )
            if not valid:
                raise AppError("invalid_credentials", "Current password is incorrect.", 403)
            developer.password_hash = await asyncio.to_thread(hash_password, data.new_password)
            # Invalidate every token issued so far, including a stolen one.
            developer.password_changed_at = datetime.now(UTC)
        await self.session.commit()
        return developer
