"""A tiny GamePulse Game API client with no third-party dependencies.

Copy this file into your own game or tool. It covers the calls a game needs: register a player,
start and end a session, send scores and events, and read a leaderboard.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
import uuid
from typing import Any


class GamePulseError(Exception):
    """The API answered with an error envelope (see docs/api-guide.md)."""

    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(f"{status} {code}: {message}")
        self.status = status
        self.code = code


class GamePulse:
    def __init__(self, base_url: str, api_key: str, timeout: float = 90.0) -> None:
        # A generous timeout covers a free-tier host waking up after being idle.
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    # -- transport ---------------------------------------------------------------------

    def _request(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> Any:
        headers = {"X-API-Key": self.api_key, "Accept": "application/json"}
        data = None
        if body is not None:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key

        for attempt in range(4):
            request = urllib.request.Request(
                f"{self.base_url}/api/v1/game{path}",
                data=data,
                headers=headers,
                method=method,
            )
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    payload = response.read()
                    return json.loads(payload) if payload else None
            except urllib.error.HTTPError as error:
                if error.code == 429 and attempt < 3:
                    # Rate limited: wait as long as the server asks, then try again.
                    time.sleep(min(float(error.headers.get("Retry-After", "1")), 30))
                    continue
                envelope = json.loads(error.read() or b"{}").get("error", {})
                raise GamePulseError(
                    error.code,
                    envelope.get("code", "error"),
                    envelope.get("message", ""),
                ) from None
        raise AssertionError("unreachable")

    # -- game API ----------------------------------------------------------------------

    def whoami(self) -> dict[str, Any]:
        """Check the API key and return the game it belongs to."""
        return self._request("GET", "/me")

    def register_player(
        self,
        external_id: str,
        username: str | None = None,
        metadata: dict | None = None,
    ) -> dict[str, Any]:
        """Idempotent: registering the same external_id again returns the existing player."""
        body: dict[str, Any] = {"external_id": external_id, "metadata": metadata or {}}
        if username:
            body["username"] = username
        return self._request("POST", "/players", body)

    def start_session(self, external_id: str, idempotency_key: str | None = None) -> dict[str, Any]:
        # An idempotency key makes a retried request safe: it cannot start two sessions. Pass your
        # own stable key to make a whole import re-runnable.
        return self._request(
            "POST",
            "/sessions",
            {"player_external_id": external_id},
            idempotency_key=idempotency_key or str(uuid.uuid4()),
        )

    def submit_score(
        self,
        external_id: str,
        value: int,
        session_id: str | None = None,
        category: str = "score",
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "player_external_id": external_id,
            "value": value,
            "category": category,
        }
        if session_id:
            body["session_id"] = session_id
        return self._request("POST", "/scores", body)

    def send_event(
        self,
        event_type: str,
        external_id: str | None = None,
        session_id: str | None = None,
        payload: dict | None = None,
        occurred_at: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """`player_level_up` or any `custom_<name>` type. The platform records the rest itself.

        `occurred_at` (ISO 8601, at most 7 days old) backdates the event.
        """
        body: dict[str, Any] = {"event_type": event_type, "payload": payload or {}}
        if occurred_at:
            body["occurred_at"] = occurred_at
        if external_id:
            body["player_external_id"] = external_id
        if session_id:
            body["session_id"] = session_id
        return self._request(
            "POST",
            "/events",
            body,
            idempotency_key=idempotency_key or str(uuid.uuid4()),
        )

    def end_session(
        self, session_id: str, score: int | None = None, result: str | None = None
    ) -> dict[str, Any]:
        """Returns the session plus `unlocked_achievements` earned by ending it."""
        body: dict[str, Any] = {}
        if score is not None:
            body["score"] = score
        if result is not None:
            body["result"] = result
        return self._request("POST", f"/sessions/{session_id}/end", body)

    def leaderboard(self, metric: str = "total_score", limit: int = 10) -> dict[str, Any]:
        return self._request("GET", f"/leaderboards/{metric}?limit={limit}")
