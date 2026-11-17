import asyncio
import json
import uuid

import httpx
import pytest
from redis.exceptions import RedisError
from sqlalchemy import text
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed

from app.core.database import get_engine, get_session_factory
from app.services.sessions import abandon_stale_sessions
from app.websocket import events, tracker
from app.websocket.hub import Connection, RealtimeHub
from tests.helpers import game_with_key, play, register_player, signup, start_session

pytestmark = pytest.mark.usefixtures("live_server")


def _token(jwt_headers: dict[str, str]) -> str:
    return jwt_headers["Authorization"].removeprefix("Bearer ")


async def open_stream(base: str, game_id: str, jwt_headers: dict[str, str]):
    ws = await connect(f"{base}/api/v1/ws/games/{game_id}")
    await ws.send(json.dumps({"type": "auth", "token": _token(jwt_headers)}))
    ready = json.loads(await asyncio.wait_for(ws.recv(), 3))
    assert ready["type"] == "ready", ready
    return ws, ready


async def collect_until(ws, event_type: str, timeout: float = 5.0) -> list[dict]:
    """Read events until one of `event_type` arrives; return everything received."""
    received: list[dict] = []
    async with asyncio.timeout(timeout):
        while True:
            message = json.loads(await ws.recv())
            received.append(message)
            if message["type"] == event_type:
                return received


async def close_code(ws) -> int:
    """Wait for the server to close the socket and return its close code."""
    with pytest.raises(ConnectionClosed) as info:
        async with asyncio.timeout(4):
            await ws.recv()
    return info.value.rcvd.code


# --- connection and authentication ----------------------------------------------------


async def test_authenticated_client_gets_ready_with_active_count(
    live_server: str, client: httpx.AsyncClient
) -> None:
    jwt, game, _ = await game_with_key(client)
    ws, ready = await open_stream(live_server, game["id"], jwt)
    assert ready == {"type": "ready", "game_id": game["id"], "active_players": 0}
    await ws.close()


async def test_ping_gets_pong(live_server: str, client: httpx.AsyncClient) -> None:
    jwt, game, _ = await game_with_key(client)
    ws, _ = await open_stream(live_server, game["id"], jwt)
    await ws.send(json.dumps({"type": "ping"}))
    assert json.loads(await asyncio.wait_for(ws.recv(), 3)) == {"type": "pong"}
    await ws.close()


@pytest.mark.parametrize(
    ("first_message", "expected_code"),
    [
        (json.dumps({"type": "auth", "token": "not.a.jwt"}), 4401),
        (json.dumps({"type": "hello"}), 4400),
        ("this is not json", 4400),
    ],
)
async def test_bad_first_message_closes_with_a_specific_code(
    live_server: str, client: httpx.AsyncClient, first_message: str, expected_code: int
) -> None:
    _, game, _ = await game_with_key(client)
    ws = await connect(f"{live_server}/api/v1/ws/games/{game['id']}")
    await ws.send(first_message)
    assert await close_code(ws) == expected_code


async def test_silent_client_is_closed_after_the_auth_timeout(
    live_server: str, client: httpx.AsyncClient
) -> None:
    _, game, _ = await game_with_key(client)
    ws = await connect(f"{live_server}/api/v1/ws/games/{game['id']}")
    assert await close_code(ws) == 4408  # WS_AUTH_TIMEOUT_SECONDS=1 in tests


async def test_another_developers_game_and_unknown_games_look_identical(
    live_server: str, client: httpx.AsyncClient
) -> None:
    _, game_a, _ = await game_with_key(client, "a@example.com", "Game A")
    jwt_b = await signup(client, "b@example.com")
    for game_id in (game_a["id"], str(uuid.uuid4())):
        ws = await connect(f"{live_server}/api/v1/ws/games/{game_id}")
        await ws.send(json.dumps({"type": "auth", "token": _token(jwt_b)}))
        assert await close_code(ws) == 4404


async def test_connection_limit_per_game(live_server: str, client: httpx.AsyncClient) -> None:
    jwt, game, _ = await game_with_key(client)
    open_sockets = [(await open_stream(live_server, game["id"], jwt))[0] for _ in range(3)]
    extra = await connect(f"{live_server}/api/v1/ws/games/{game['id']}")
    await extra.send(json.dumps({"type": "auth", "token": _token(jwt)}))
    assert await close_code(extra) == 4429

    await open_sockets[0].close()
    await asyncio.sleep(0.2)  # let the server unregister the closed socket
    again, _ = await open_stream(live_server, game["id"], jwt)
    for ws in (*open_sockets[1:], again):
        await ws.close()


# --- events ---------------------------------------------------------------------------


async def test_a_full_play_flow_is_pushed_in_order(
    live_server: str, client: httpx.AsyncClient
) -> None:
    jwt, game, key = await game_with_key(client)
    ws, _ = await open_stream(live_server, game["id"], jwt)

    await register_player(client, key, "p1", username="Ada")
    session = (await start_session(client, key, "p1")).json()
    await client.post(
        "/api/v1/game/scores",
        json={"player_external_id": "p1", "value": 700, "session_id": session["id"]},
        headers=key,
    )
    await client.post(
        f"/api/v1/game/sessions/{session['id']}/end",
        json={"score": 1500, "result": "win"},
        headers=key,
    )

    received = await collect_until(ws, "leaderboard.updated")
    types = [e["type"] for e in received]
    assert types[:4] == ["player.registered", "session.started", "score.submitted", "session.ended"]
    assert types[-1] == "leaderboard.updated"
    assert "achievement.unlocked" in types

    by_type = {e["type"]: e for e in received}
    for envelope in received:  # every event has the same envelope
        assert {"id", "type", "game_id", "ts", "is_simulated", "data"} <= envelope.keys()
        assert envelope["game_id"] == game["id"] and envelope["is_simulated"] is False
    assert by_type["session.started"]["data"]["active_players"] == 1
    assert by_type["session.ended"]["data"]["session"]["score"] == 1500
    assert by_type["session.ended"]["data"]["active_players"] == 0
    assert by_type["score.submitted"]["data"]["value"] == 700
    assert by_type["leaderboard.updated"]["data"]["rank"] == 1
    unlocked = [
        e["data"]["achievement"]["key"] for e in received if e["type"] == "achievement.unlocked"
    ]
    assert "first_game" in unlocked and "high_scorer" in unlocked
    await ws.close()


async def test_idempotent_replays_do_not_emit_duplicate_events(
    live_server: str, client: httpx.AsyncClient
) -> None:
    jwt, game, key = await game_with_key(client)
    ws, _ = await open_stream(live_server, game["id"], jwt)
    await register_player(client, key)
    await start_session(client, key, idempotency_key="same")
    await start_session(client, key, idempotency_key="same")  # replay

    received = await collect_until(ws, "session.started")
    assert [e["type"] for e in received] == ["player.registered", "session.started"]
    with pytest.raises(TimeoutError):
        async with asyncio.timeout(0.7):
            await ws.recv()  # no second session.started
    await ws.close()


async def test_events_are_delivered_only_to_the_games_owner(
    live_server: str, client: httpx.AsyncClient
) -> None:
    jwt_a, game_a, key_a = await game_with_key(client, "a@example.com", "Game A")
    jwt_b, game_b, _ = await game_with_key(client, "b@example.com", "Game B")
    ws_a, _ = await open_stream(live_server, game_a["id"], jwt_a)
    ws_b, _ = await open_stream(live_server, game_b["id"], jwt_b)

    await register_player(client, key_a, "p1")
    assert (await collect_until(ws_a, "player.registered"))[0]["game_id"] == game_a["id"]
    with pytest.raises(TimeoutError):
        async with asyncio.timeout(0.7):
            await ws_b.recv()  # game B's dashboard sees nothing from game A
    await ws_a.close()
    await ws_b.close()


async def test_reaper_pushes_session_abandoned(live_server: str, client: httpx.AsyncClient) -> None:
    jwt, game, key = await game_with_key(client)
    ws, _ = await open_stream(live_server, game["id"], jwt)
    await register_player(client, key)
    session = (await start_session(client, key)).json()
    async with get_engine().begin() as conn:
        await conn.execute(
            text(
                "UPDATE game_sessions SET started_at = now() - interval '2 hours', "
                "last_heartbeat_at = now() - interval '1 hour' WHERE id=:i"
            ),
            {"i": session["id"]},
        )
    async with get_session_factory()() as db:
        assert await abandon_stale_sessions(db) == 1

    received = await collect_until(ws, "session.abandoned")
    assert received[-1]["data"]["session"]["id"] == session["id"]
    assert received[-1]["data"]["active_players"] == 0
    await ws.close()


async def test_request_succeeds_even_if_redis_publish_fails(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, _, key = await game_with_key(client)

    class BrokenRedis:
        async def publish(self, *_args, **_kwargs):
            raise RedisError("down")

    monkeypatch.setattr(events, "get_redis", lambda: BrokenRedis())
    registered = await client.post("/api/v1/game/players", json={"external_id": "p1"}, headers=key)
    assert registered.status_code == 201  # real-time is best-effort


# --- hub unit tests -------------------------------------------------------------------


async def test_hub_drops_a_slow_consumer_instead_of_blocking() -> None:
    hub = RealtimeHub(max_connections_per_game=5)
    game_id = uuid.uuid4()
    slow = Connection.create(None, game_id, queue_size=2)
    fast = Connection.create(None, game_id, queue_size=50)
    other_game = Connection.create(None, uuid.uuid4(), queue_size=2)
    for connection in (slow, fast, other_game):
        assert hub.register(connection)

    for n in range(3):  # third message overflows the slow consumer's queue of 2
        hub.dispatch(game_id, f"msg-{n}")

    assert slow.overflowed is True and fast.overflowed is False
    assert slow.queue.get_nowait() is None  # sentinel: sender task stops
    assert fast.queue.qsize() == 3
    assert other_game.queue.empty()  # other games never receive it
    assert hub.connection_count(game_id) == 1  # slow connection was removed


def test_hub_enforces_the_per_game_limit() -> None:
    hub = RealtimeHub(max_connections_per_game=2)
    game_id = uuid.uuid4()
    connections = [Connection.create(None, game_id, 5) for _ in range(3)]
    assert [hub.register(c) for c in connections] == [True, True, False]
    hub.unregister(connections[0])
    assert hub.register(connections[2]) is True


def test_channel_names_round_trip() -> None:
    game_id = uuid.uuid4()
    assert events.game_id_from_channel(events.channel_for(game_id)) == game_id
    for bad in ("gp:game:nope:events", "other:game:x:events", "gp:game:events"):
        assert events.game_id_from_channel(bad) is None


# --- active player tracking -----------------------------------------------------------


async def _live(client: httpx.AsyncClient, jwt: dict, game_id: str) -> dict:
    response = await client.get(f"/api/v1/games/{game_id}/live", headers=jwt)
    assert response.status_code == 200
    return response.json()


async def test_active_players_follow_session_lifecycle(client: httpx.AsyncClient) -> None:
    jwt, game, key = await game_with_key(client)
    await register_player(client, key, "p1")
    await register_player(client, key, "p2")
    assert (await _live(client, jwt, game["id"]))["active_players"] == 0

    s1 = (await start_session(client, key, "p1")).json()
    await start_session(client, key, "p2")
    live = await _live(client, jwt, game["id"])
    assert live["active_players"] == 2 and live["source"] == "redis"

    await client.post(f"/api/v1/game/sessions/{s1['id']}/end", json={}, headers=key)
    assert (await _live(client, jwt, game["id"]))["active_players"] == 1


async def test_stale_players_stop_counting_without_waiting_for_the_reaper(
    client: httpx.AsyncClient,
) -> None:
    from app.core.redis import get_redis

    jwt, game, key = await game_with_key(client)
    await register_player(client, key)
    await start_session(client, key)
    assert (await _live(client, jwt, game["id"]))["active_players"] == 1

    # Backdate the player's heartbeat in Redis beyond the 15 minute timeout.
    redis_key = f"gp:game:{game['id']}:active"
    (member,) = await get_redis().zrange(redis_key, 0, -1)
    await get_redis().zadd(redis_key, {member: 1.0})
    assert (await _live(client, jwt, game["id"]))["active_players"] == 0


async def test_redis_is_rebuilt_from_postgres(client: httpx.AsyncClient) -> None:
    from app.core.redis import get_redis

    jwt, game, key = await game_with_key(client)
    for name in ("p1", "p2"):
        await register_player(client, key, name)
        await start_session(client, key, name)
    await get_redis().flushdb()  # simulate a Redis restart
    assert (await _live(client, jwt, game["id"]))["active_players"] == 0

    async with get_session_factory()() as db:
        assert await tracker.rebuild(db) == 2
    assert (await _live(client, jwt, game["id"]))["active_players"] == 2


async def test_live_count_falls_back_to_postgres_when_redis_fails(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    jwt, game, key = await game_with_key(client)
    await register_player(client, key)
    await start_session(client, key)

    async def redis_down(_game_id):
        return None

    monkeypatch.setattr(tracker, "count_from_redis", redis_down)
    live = await _live(client, jwt, game["id"])
    assert live == {"active_players": 1, "source": "postgres", "dashboards_connected": 0}


async def test_live_stats_are_scoped_to_the_owner(client: httpx.AsyncClient) -> None:
    _, game_a, _ = await game_with_key(client, "a@example.com", "Game A")
    jwt_b = await signup(client, "b@example.com")
    response = await client.get(f"/api/v1/games/{game_a['id']}/live", headers=jwt_b)
    assert response.status_code == 404


# --- leaderboard cache ----------------------------------------------------------------


async def test_leaderboard_is_cached_and_invalidated_by_new_scores(
    client: httpx.AsyncClient,
) -> None:
    from app.core.redis import get_redis

    _, game, key = await game_with_key(client)
    await play(client, key, "ada", 500, "win")
    url = "/api/v1/game/leaderboards/total_score"
    first = (await client.get(url, headers=key)).json()
    assert first["items"][0]["value"] == 500
    assert await get_redis().keys(f"gp:game:{game['id']}:lb:*")  # entry was cached

    # Change the database behind the cache's back: the cached page is still served.
    async with get_engine().begin() as conn:
        await conn.execute(text("UPDATE player_stats SET total_score = 1"))
    assert (await client.get(url, headers=key)).json() == first

    # A real score change bumps the version, so the next read recomputes.
    await play(client, key, "bob", 800, "win")
    fresh = (await client.get(url, headers=key)).json()
    assert [(e["player"]["username"], e["value"]) for e in fresh["items"]] == [
        ("bob", 800),
        ("ada", 1),
    ]


async def test_leaderboard_works_when_the_cache_is_down(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.services import leaderboards

    _, _, key = await game_with_key(client)
    await play(client, key, "ada", 500)

    class BrokenRedis:
        async def get(self, *_a, **_k):
            raise RedisError("down")

        incr = set = get

    monkeypatch.setattr(leaderboards, "get_redis", lambda: BrokenRedis())
    response = await client.get("/api/v1/game/leaderboards/total_score", headers=key)
    assert response.status_code == 200 and response.json()["items"][0]["value"] == 500
