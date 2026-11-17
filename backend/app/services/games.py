import re
import unicodedata
import uuid
from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.security import api_key_matches, generate_api_key, parse_api_key_prefix
from app.models import ApiKey, Developer, Game
from app.repositories.api_keys import ApiKeyRepository
from app.repositories.games import GameRepository
from app.schemas.game import GameCreate, GameUpdate
from app.services.achievements import seed_default_achievements

LAST_USED_REFRESH_SECONDS = 60


def slugify(name: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")
    return slug[:100] or "game"


def _invalid_api_key() -> AppError:
    return AppError(
        "invalid_api_key",
        "Missing or invalid API key.",
        401,
        headers={"WWW-Authenticate": "ApiKey"},
    )


class GameService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.games = GameRepository(session)
        self.keys = ApiKeyRepository(session)

    # --- games -----------------------------------------------------------------------

    async def create_game(self, developer: Developer, data: GameCreate) -> Game:
        base = slugify(data.name)
        slug, suffix = base, 1
        while await self.games.slug_exists(developer.id, slug):
            suffix += 1
            slug = f"{base}-{suffix}"
        game = Game(
            id=uuid.uuid4(),
            developer_id=developer.id,
            name=data.name.strip(),
            slug=slug,
            description=data.description,
            genre=data.genre,
        )
        self.games.add(game)
        try:
            # Flush the game first: achievement rows reference it and the ORM has no
            # relationship to order the inserts for us.
            await self.session.flush()
            seed_default_achievements(self.session, game.id)
            await self.session.commit()
        except IntegrityError:  # concurrent create took the slug
            await self.session.rollback()
            raise AppError("slug_conflict", "Please retry: game name collided.", 409) from None
        return game

    async def update_game(self, game: Game, data: GameUpdate) -> Game:
        for field, value in data.model_dump(exclude_unset=True).items():
            if field == "name":
                value = (value or game.name).strip()
            setattr(game, field, value)
        await self.session.commit()
        await self.session.refresh(game)
        return game

    async def delete_game(self, game: Game) -> None:
        await self.games.soft_delete(game)
        await self.session.commit()

    # --- api keys --------------------------------------------------------------------

    async def create_key(self, game: Game, name: str) -> tuple[ApiKey, str]:
        full_key, prefix, key_hash = generate_api_key()
        key = ApiKey(game_id=game.id, name=name.strip(), key_prefix=prefix, key_hash=key_hash)
        self.keys.add(key)
        await self.session.commit()
        await self.session.refresh(key)
        return key, full_key

    async def rotate_key(self, game: Game, key_id: uuid.UUID) -> tuple[ApiKey, str]:
        old = await self._get_key(game, key_id)
        if old.revoked_at is not None:
            raise AppError("key_revoked", "This key is already revoked; create a new one.", 409)
        old.revoked_at = datetime.now(UTC)
        full_key, prefix, key_hash = generate_api_key()
        new = ApiKey(game_id=game.id, name=old.name, key_prefix=prefix, key_hash=key_hash)
        self.keys.add(new)
        await self.session.commit()
        await self.session.refresh(new)
        return new, full_key

    async def revoke_key(self, game: Game, key_id: uuid.UUID) -> None:
        key = await self._get_key(game, key_id)
        if key.revoked_at is None:  # revoking twice is a harmless no-op
            key.revoked_at = datetime.now(UTC)
            await self.session.commit()

    async def _get_key(self, game: Game, key_id: uuid.UUID) -> ApiKey:
        key = await self.keys.get_for_game(game.id, key_id)
        if key is None:
            raise AppError("api_key_not_found", "API key not found.", 404)
        return key

    async def authenticate_api_key(self, full_key: str | None) -> Game:
        """Resolve an `X-API-Key` header value to its game, or raise 401."""
        if not full_key:
            raise _invalid_api_key()
        prefix = parse_api_key_prefix(full_key)
        found = await self.keys.get_active_with_game(prefix) if prefix else None
        if found is None or not api_key_matches(full_key, found[0].key_hash):
            raise _invalid_api_key()
        key, game = found
        now = datetime.now(UTC)
        stale = key.last_used_at is None or (
            (now - key.last_used_at).total_seconds() >= LAST_USED_REFRESH_SECONDS
        )
        if stale:
            key.last_used_at = now  # throttled so auth doesn't write on every request
            await self.session.commit()
        return game
