import asyncio
import json
import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy.exc import IntegrityError
from websockets.asyncio.client import connect

from app.core.config import get_settings
from tests.helpers import (
    game_with_key,
    play,
    register_player,
    signup,
    sql,
    sql_all,
    start_session,
)


async def _ingest(client: httpx.AsyncClient, key: dict, idem: str | None = None, **body):
    headers = dict(key)
    if idem:
        headers["Idempotency-Key"] = idem
    return await client.post("/api/v1/game/events", json=body, headers=headers)


async def _log(client: httpx.AsyncClient, jwt: dict, game_id: str, query: str = "") -> dict:
    response = await client.get(f"/api/v1/games/{game_id}/events?{query}", headers=jwt)
    assert response.status_code == 200, response.text
    return response.json()


# --- the platform records its own events ------------------------------------------------


async def test_platform_actions_are_recorded_as_events(client: httpx.AsyncClient) -> None:
    jwt, game, key = await game_with_key(client)
    await register_player(client, key, "p1", username="Ada")
    session = (await start_session(client, key, "p1")).json()
    await client.post(
        "/api/v1/game/scores",
        json={"player_external_id": "p1", "value": 50, "session_id": session["id"]},
        headers=key,
    )
    await client.post(
        f"/api/v1/game/sessions/{session['id']}/end",
        json={"score": 90, "result": "win"},
        headers=key,
    )

    log = await _log(client, jwt, game["id"], "limit=100")
    by_type: dict[str, list] = {}
    for event in log["items"]:
        by_type.setdefault(event["event_type"], []).append(event)

    assert set(by_type) == {
        "player_registered",
        "session_started",
        "score_submitted",
        "session_ended",
        "achievement_unlocked",
    }
    assert by_type["player_registered"][0]["payload"]["username"] == "Ada"
    assert by_type["session_started"][0]["session_id"] == session["id"]
    assert by_type["score_submitted"][0]["payload"] == {"category": "score", "value": 50}
    ended = by_type["session_ended"][0]["payload"]
    assert ended["score"] == 90 and ended["result"] == "win" and ended["duration_seconds"] >= 0
    assert by_type["achievement_unlocked"][0]["payload"]["key"] == "first_game"
    assert all(e["player"]["external_id"] == "p1" for e in log["items"])
    assert all(e["is_simulated"] is False for e in log["items"])


async def test_idempotent_replays_do_not_create_duplicate_events(client: httpx.AsyncClient) -> None:
    jwt, game, key = await game_with_key(client)
    await register_player(client, key)
    await register_player(client, key)  # replay: no second player_registered
    await start_session(client, key, idempotency_key="s")
    await start_session(client, key, idempotency_key="s")  # replay: no second session_started
    counts = {e["event_type"] for e in (await _log(client, jwt, game["id"]))["items"]}
    log = (await _log(client, jwt, game["id"]))["items"]
    assert counts == {"player_registered", "session_started"}
    assert len(log) == 2


async def test_event_log_filters_order_and_pagination(client: httpx.AsyncClient) -> None:
    jwt, game, key = await game_with_key(client)
    r1 = await play(client, key, "p1", 10)
    await play(client, key, "p2", 20)
    base = game["id"]

    everything = await _log(client, jwt, base, "limit=100")
    times = [e["occurred_at"] for e in everything["items"]]
    assert times == sorted(times, reverse=True)  # newest first

    started = await _log(client, jwt, base, "event_type=session_started")
    assert started["total"] == 2
    page = await _log(client, jwt, base, "limit=2&offset=0")
    assert len(page["items"]) == 2 and page["total"] == everything["total"]

    by_session = await _log(client, jwt, base, f"session_id={r1['id']}")
    assert {e["event_type"] for e in by_session["items"]} >= {"session_started", "session_ended"}

    player = (await client.get(f"/api/v1/games/{base}/players?q=p1", headers=jwt)).json()["items"][
        0
    ]
    timeline = await _log(client, jwt, base, f"player_id={player['id']}")
    assert timeline["total"] > 0
    assert {e["player"]["external_id"] for e in timeline["items"]} == {"p1"}

    future = (datetime.now(UTC) + timedelta(hours=1)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )  # '+' would need URL encoding
    assert (await _log(client, jwt, base, f"since={future}"))["total"] == 0


async def test_simulated_events_can_be_excluded(client: httpx.AsyncClient) -> None:
    jwt, game, key = await game_with_key(client)
    await play(client, key, "real", 10)
    await play(client, key, "fake", 10)
    await sql(
        "UPDATE events SET is_simulated = true WHERE player_id IN "
        "(SELECT id FROM players WHERE external_id = 'fake')"
    )
    all_events = await _log(client, jwt, game["id"], "limit=100")
    real_only = await _log(client, jwt, game["id"], "include_simulated=false&limit=100")
    assert 0 < real_only["total"] < all_events["total"]
    assert all(e["is_simulated"] is False for e in real_only["items"])


# --- ingestion ----------------------------------------------------------------------------


async def test_ingest_custom_event_and_player_level_up(client: httpx.AsyncClient) -> None:
    jwt, game, key = await game_with_key(client)
    await register_player(client, key, "p1")

    custom = await _ingest(
        client,
        key,
        event_type="custom_boss_defeated",
        player_external_id="p1",
        payload={"boss": "kraken", "seconds": 42},
    )
    assert custom.status_code == 201
    body = custom.json()
    assert body["event_type"] == "custom_boss_defeated" and body["payload"]["boss"] == "kraken"
    assert body["player_id"] is not None and body["is_simulated"] is False

    level = await _ingest(
        client,
        key,
        event_type="player_level_up",
        player_external_id="p1",
        payload={"level": 5, "previous_level": 4},
    )
    assert level.status_code == 201 and level.json()["payload"] == {"level": 5, "previous_level": 4}

    log = await _log(client, jwt, game["id"], "event_type=custom_boss_defeated")
    assert log["total"] == 1 and log["items"][0]["player"]["external_id"] == "p1"


async def test_event_without_a_player_is_allowed(client: httpx.AsyncClient) -> None:
    _, _, key = await game_with_key(client)
    response = await _ingest(
        client, key, event_type="custom_server_started", payload={"build": "1.2"}
    )
    assert response.status_code == 201 and response.json()["player_id"] is None


async def test_session_id_alone_resolves_the_player(client: httpx.AsyncClient) -> None:
    _, _, key = await game_with_key(client)
    await register_player(client, key, "p1")
    session = (await start_session(client, key, "p1")).json()
    response = await _ingest(client, key, event_type="custom_pickup", session_id=session["id"])
    assert response.status_code == 201
    assert response.json()["player_id"] == session["player"]["id"]


async def test_occurred_at_is_stored_when_reasonable(client: httpx.AsyncClient) -> None:
    _, _, key = await game_with_key(client)
    two_days_ago = datetime.now(UTC) - timedelta(days=2)
    response = await _ingest(
        client, key, event_type="custom_offline_sync", occurred_at=two_days_ago.isoformat()
    )
    assert response.status_code == 201
    stored = datetime.fromisoformat(response.json()["occurred_at"].replace("Z", "+00:00"))
    assert abs((stored - two_days_ago).total_seconds()) < 1
    assert response.json()["received_at"] > response.json()["occurred_at"]


@pytest.mark.parametrize(
    "event_type",
    [
        "player_registered",
        "session_started",
        "session_ended",
        "score_submitted",
        "achievement_unlocked",
    ],
)
async def test_system_event_types_are_reserved(client: httpx.AsyncClient, event_type: str) -> None:
    _, _, key = await game_with_key(client)
    response = await _ingest(client, key, event_type=event_type)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "reserved_event_type"


@pytest.mark.parametrize(
    "event_type", ["boss_defeated", "custom_", "custom_Bad", "custom_a-b", "x"]
)
async def test_unknown_or_malformed_event_types_are_rejected(
    client: httpx.AsyncClient, event_type: str
) -> None:
    _, _, key = await game_with_key(client)
    response = await _ingest(client, key, event_type=event_type)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "unknown_event_type"


@pytest.mark.parametrize(
    "payload", [{}, {"level": 0}, {"level": "five"}, {"level": 3, "cheat": True}]
)
async def test_level_up_payload_is_validated(client: httpx.AsyncClient, payload: dict) -> None:
    _, _, key = await game_with_key(client)
    response = await _ingest(client, key, event_type="player_level_up", payload=payload)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_payload"
    assert response.json()["error"]["details"]


async def test_payload_size_and_time_range_limits(client: httpx.AsyncClient) -> None:
    _, _, key = await game_with_key(client)
    huge = await _ingest(client, key, event_type="custom_big", payload={"blob": "a" * 9000})
    assert huge.status_code == 422
    for when in (datetime.now(UTC) - timedelta(days=8), datetime.now(UTC) + timedelta(hours=1)):
        response = await _ingest(
            client, key, event_type="custom_time", occurred_at=when.isoformat()
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "occurred_at_out_of_range"


async def test_unknown_player_or_session_is_404(client: httpx.AsyncClient) -> None:
    _, _, key = await game_with_key(client)
    ghost = await _ingest(client, key, event_type="custom_x", player_external_id="ghost")
    assert ghost.status_code == 404 and ghost.json()["error"]["code"] == "player_not_found"
    no_session = await _ingest(client, key, event_type="custom_x", session_id=str(uuid.uuid4()))
    assert (
        no_session.status_code == 404 and no_session.json()["error"]["code"] == "session_not_found"
    )

    await register_player(client, key, "p1")
    await register_player(client, key, "p2")
    s1 = (await start_session(client, key, "p1")).json()
    mismatch = await _ingest(
        client, key, event_type="custom_x", player_external_id="p2", session_id=s1["id"]
    )
    assert mismatch.status_code == 404


async def test_ingestion_requires_a_key(client: httpx.AsyncClient) -> None:
    response = await client.post("/api/v1/game/events", json={"event_type": "custom_x"})
    assert response.status_code == 401


# --- idempotency ----------------------------------------------------------------------------


async def test_idempotency_key_replays_without_duplicating(client: httpx.AsyncClient) -> None:
    jwt, game, key = await game_with_key(client)
    first = await _ingest(client, key, "evt-1", event_type="custom_once", payload={"n": 1})
    replay = await _ingest(client, key, "evt-1", event_type="custom_once", payload={"n": 1})
    assert (first.status_code, replay.status_code) == (201, 200)
    assert first.json()["id"] == replay.json()["id"]
    assert (await _log(client, jwt, game["id"], "event_type=custom_once"))["total"] == 1


async def test_idempotency_key_cannot_be_reused_for_a_different_event(
    client: httpx.AsyncClient,
) -> None:
    _, _, key = await game_with_key(client)
    await _ingest(client, key, "evt-1", event_type="custom_a")
    clash = await _ingest(client, key, "evt-1", event_type="custom_b")
    assert clash.status_code == 409 and clash.json()["error"]["code"] == "idempotency_key_reused"


async def test_concurrent_requests_with_one_key_create_one_event(client: httpx.AsyncClient) -> None:
    jwt, game, key = await game_with_key(client)
    results = await asyncio.gather(
        *[_ingest(client, key, "same", event_type="custom_race") for _ in range(5)]
    )
    assert sorted(r.status_code for r in results).count(201) == 1
    assert all(r.status_code in (200, 201) for r in results)
    assert (await _log(client, jwt, game["id"], "event_type=custom_race"))["total"] == 1


async def test_same_key_in_two_games_is_independent(client: httpx.AsyncClient) -> None:
    _, _, key_a = await game_with_key(client, "a@example.com", "Game A")
    _, _, key_b = await game_with_key(client, "b@example.com", "Game B")
    a = await _ingest(client, key_a, "shared", event_type="custom_x")
    b = await _ingest(client, key_b, "shared", event_type="custom_x")
    assert (a.status_code, b.status_code) == (201, 201) and a.json()["id"] != b.json()["id"]


# --- isolation --------------------------------------------------------------------------------


async def test_event_log_and_ingestion_are_tenant_scoped(client: httpx.AsyncClient) -> None:
    jwt_a, game_a, key_a = await game_with_key(client, "a@example.com", "Game A")
    jwt_b, game_b, key_b = await game_with_key(client, "b@example.com", "Game B")
    await register_player(client, key_a, "p1")
    session_a = (await start_session(client, key_a, "p1")).json()

    assert (
        await client.get(f"/api/v1/games/{game_a['id']}/events", headers=jwt_b)
    ).status_code == 404
    assert (await _log(client, jwt_b, game_b["id"]))["total"] == 0  # nothing from game A leaks

    # Game B's key cannot attach events to game A's player or session.
    by_player = await _ingest(client, key_b, event_type="custom_x", player_external_id="p1")
    by_session = await _ingest(client, key_b, event_type="custom_x", session_id=session_a["id"])
    assert by_player.status_code == 404 and by_session.status_code == 404


async def test_database_rejects_cross_game_event_rows(client: httpx.AsyncClient) -> None:
    from sqlalchemy import text

    from app.core.database import get_engine

    _, game_a, key_a = await game_with_key(client, "a@example.com", "Game A")
    _, game_b, _ = await game_with_key(client, "b@example.com", "Game B")
    player = await register_player(client, key_a, "p1")
    with pytest.raises(IntegrityError):
        async with get_engine().begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO events (id, game_id, player_id, event_type) "
                    "VALUES (:id, :g, :p, 'custom_x')"
                ),
                {"id": uuid.uuid4(), "g": game_b["id"], "p": player["id"]},
            )
    with pytest.raises(IntegrityError):  # event_type format check
        async with get_engine().begin() as conn:
            await conn.execute(
                text("INSERT INTO events (id, game_id, event_type) VALUES (:id, :g, 'Bad Type!')"),
                {"id": uuid.uuid4(), "g": game_a["id"]},
            )


# --- rate limiting and real time ----------------------------------------------------------------


async def test_game_api_is_rate_limited_per_game(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, _, key_a = await game_with_key(client, "a@example.com", "Game A")
    _, _, key_b = await game_with_key(client, "b@example.com", "Game B")
    monkeypatch.setenv("GAME_API_RATE_LIMIT_PER_MINUTE", "3")
    get_settings.cache_clear()
    try:
        statuses = [
            (await _ingest(client, key_a, event_type="custom_x")).status_code for _ in range(5)
        ]
        assert statuses == [201, 201, 201, 429, 429]
        limited = await _ingest(client, key_a, event_type="custom_x")
        assert limited.json()["error"]["code"] == "rate_limited"
        assert int(limited.headers["Retry-After"]) > 0
        # Another game has its own budget.
        assert (await _ingest(client, key_b, event_type="custom_x")).status_code == 201
        # Requests with a bad key are rejected as 401 and never consume a game's budget.
        assert (
            await client.get("/api/v1/game/me", headers={"X-API-Key": "bad"})
        ).status_code == 401
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()


async def test_ingested_events_are_pushed_to_dashboards(
    live_server: str, client: httpx.AsyncClient
) -> None:
    jwt, game, key = await game_with_key(client)
    ws = await connect(f"{live_server}/api/v1/ws/games/{game['id']}")
    await ws.send(json.dumps({"type": "auth", "token": jwt["Authorization"].split()[1]}))
    assert json.loads(await ws.recv())["type"] == "ready"

    await _ingest(client, key, event_type="custom_boss", payload={"hp": 0})
    async with asyncio.timeout(4):
        message = json.loads(await ws.recv())
    assert message["type"] == "event.received"
    assert message["data"]["event"]["event_type"] == "custom_boss"
    assert message["data"]["event"]["payload"] == {"hp": 0}
    await ws.close()


async def test_stored_events_match_the_database(client: httpx.AsyncClient) -> None:
    _, game, key = await game_with_key(client)
    await play(client, key, "p1", 10)
    await _ingest(client, key, event_type="custom_x")
    rows = await sql_all(
        "SELECT event_type, count(*) FROM events WHERE game_id = :g GROUP BY 1", g=game["id"]
    )
    assert dict(rows) == {
        "player_registered": 1,
        "session_started": 1,
        "session_ended": 1,
        "achievement_unlocked": 1,
        "custom_x": 1,
    }


_ = (signup,)  # imported for parity with other test modules
