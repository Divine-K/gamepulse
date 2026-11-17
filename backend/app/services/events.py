"""Event ingestion for externally reported events."""

import uuid
from datetime import UTC, datetime, timedelta

from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models import Event, Game
from app.models.event import SYSTEM_EVENT_TYPES
from app.repositories.events import EventRepository
from app.repositories.players import PlayerRepository
from app.repositories.sessions import SessionRepository
from app.schemas.event import CUSTOM_EVENT_PATTERN, KNOWN_PAYLOAD_MODELS, EventCreate
from app.services.event_log import record_event
from app.websocket import events as realtime

MAX_AGE = timedelta(days=7)
MAX_FUTURE = timedelta(minutes=5)  # tolerate small client clock skew


def validate_event_type_and_payload(data: EventCreate) -> dict:
    """Return the cleaned payload, or raise a 422 explaining what is allowed."""
    event_type = data.event_type
    if event_type in SYSTEM_EVENT_TYPES:
        raise AppError(
            "reserved_event_type",
            f"'{event_type}' is recorded automatically by GamePulse when you use the "
            "players, sessions and scores endpoints. Send custom_* or player_level_up events here.",
            422,
        )
    model = KNOWN_PAYLOAD_MODELS.get(event_type)
    if model is not None:
        try:
            return model.model_validate(data.payload).model_dump(exclude_none=True)
        except ValidationError as exc:
            raise AppError(
                "invalid_payload",
                f"Invalid payload for '{event_type}'.",
                422,
                details=[
                    {"field": ".".join(str(p) for p in e["loc"]), "message": e["msg"]}
                    for e in exc.errors()
                ],
            ) from None
    if not CUSTOM_EVENT_PATTERN.match(event_type):
        raise AppError(
            "unknown_event_type",
            "Event types are 'player_level_up' or 'custom_<name>' (lowercase letters, digits, "
            "underscores).",
            422,
        )
    return data.payload


class EventService:
    def __init__(self, session: AsyncSession, game: Game) -> None:
        self.session = session
        self.game = game
        self.game_id = game.id  # plain id: safe after a rollback expires ORM objects
        self.events = EventRepository(session)
        self.players = PlayerRepository(session)
        self.sessions = SessionRepository(session)

    async def ingest(self, data: EventCreate, idempotency_key: str | None) -> tuple[Event, bool]:
        """Validate and store an event. Returns (event, created); created=False on a replay."""
        payload = validate_event_type_and_payload(data)
        occurred_at = self._check_time(data.occurred_at)

        player_id: uuid.UUID | None = None
        simulated = False
        if data.player_external_id is not None:
            player = await self.players.get_by_external_id(self.game_id, data.player_external_id)
            if player is None:
                raise AppError("player_not_found", "Player not found.", 404)
            player_id, simulated = player.id, player.is_simulated

        session_id = data.session_id
        if session_id is not None:
            game_session = await self.sessions.get(self.game_id, session_id)
            if game_session is None or (player_id and game_session.player_id != player_id):
                raise AppError("session_not_found", "Session not found for this player.", 404)
            player_id = player_id or game_session.player_id
            simulated = game_session.is_simulated

        if idempotency_key:
            replay = await self._replay(idempotency_key, data.event_type, player_id)
            if replay:
                return replay, False

        event = record_event(
            self.session,
            game_id=self.game_id,
            event_type=data.event_type,
            player_id=player_id,
            session_id=session_id,
            payload=payload,
            is_simulated=simulated,
            occurred_at=occurred_at,
            idempotency_key=idempotency_key,
        )
        try:
            await self.session.commit()
        except IntegrityError:  # a concurrent request used the same Idempotency-Key
            await self.session.rollback()
            if idempotency_key:
                replay = await self._replay(idempotency_key, data.event_type, player_id)
                if replay:
                    return replay, False
            raise
        await self.session.refresh(event)
        await realtime.publish(
            self.game_id,
            realtime.EVENT_RECEIVED,
            {
                "event": {
                    "id": str(event.id),
                    "event_type": event.event_type,
                    "player_id": str(event.player_id) if event.player_id else None,
                    "session_id": str(event.session_id) if event.session_id else None,
                    "occurred_at": event.occurred_at.isoformat(),
                    "payload": event.payload,
                }
            },
            is_simulated=event.is_simulated,
        )
        return event, True

    @staticmethod
    def _check_time(occurred_at: datetime | None) -> datetime | None:
        if occurred_at is None:
            return None
        if occurred_at.tzinfo is None:
            occurred_at = occurred_at.replace(tzinfo=UTC)
        now = datetime.now(UTC)
        if occurred_at < now - MAX_AGE or occurred_at > now + MAX_FUTURE:
            raise AppError(
                "occurred_at_out_of_range",
                "occurred_at must be within the last 7 days and not in the future.",
                422,
            )
        return occurred_at

    async def _replay(self, key: str, event_type: str, player_id: uuid.UUID | None) -> Event | None:
        existing = await self.events.get_by_idempotency_key(self.game_id, key)
        if existing is None:
            return None
        if existing.event_type != event_type or existing.player_id != player_id:
            raise AppError(
                "idempotency_key_reused",
                "This Idempotency-Key was already used for a different event.",
                409,
            )
        return existing
