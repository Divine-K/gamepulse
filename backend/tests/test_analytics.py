import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from tests.helpers import game_with_key, play, register_player, sql, start_session

BASE = "/api/v1/games/{}/analytics"


async def _get(client: httpx.AsyncClient, jwt: dict, game_id: str, path: str, query: str = ""):
    response = await client.get(f"{BASE.format(game_id)}/{path}?{query}", headers=jwt)
    assert response.status_code == 200, response.text
    return response.json()


async def shift_player(external_id: str, days: float) -> None:
    """Move everything a player did `days` into the past (registration, sessions, events)."""
    interval = f"make_interval(secs => {int(days * 86400)})"
    where = "(SELECT id FROM players WHERE external_id = :e)"
    await sql(
        f"UPDATE events SET occurred_at = occurred_at - {interval} WHERE player_id = {where}",
        e=external_id,
    )
    await sql(
        f"UPDATE game_sessions SET started_at = started_at - {interval}, "
        f"ended_at = ended_at - {interval}, last_heartbeat_at = last_heartbeat_at - {interval} "
        f"WHERE player_id = {where}",
        e=external_id,
    )
    await sql(
        f"UPDATE players SET created_at = created_at - {interval} WHERE id = {where}", e=external_id
    )
    await sql(
        f"UPDATE player_achievements SET unlocked_at = unlocked_at - {interval} WHERE player_id = {where}",
        e=external_id,
    )


# --- empty and basic ----------------------------------------------------------------------


async def test_empty_game_returns_zeros_not_errors(client: httpx.AsyncClient) -> None:
    jwt, game, _ = await game_with_key(client)
    gid = game["id"]

    overview = await _get(client, jwt, gid, "overview")
    assert overview["total_players"] == overview["total_sessions"] == overview["total_events"] == 0
    assert overview["avg_session_duration_seconds"] is None
    assert overview["daily_active_players"] == overview["monthly_active_players"] == 0
    assert overview["currently_active_players"] == 0

    engagement = await _get(client, jwt, gid, "engagement", "days=7")
    assert len(engagement["points"]) == 7
    assert all(
        p["events"] == 0 and p["avg_session_duration_seconds"] is None for p in engagement["points"]
    )

    retention = await _get(client, jwt, gid, "retention")
    assert [p["rate"] for p in retention["points"]] == [None, None, None]

    scores = await _get(client, jwt, gid, "scores")
    assert (
        scores["completed_sessions"] == 0 and scores["buckets"] == [] and scores["median"] is None
    )

    achievements = await _get(client, jwt, gid, "achievements")
    assert achievements["total_unlocks"] == 0 and len(achievements["achievements"]) == 6


async def test_overview_totals_come_from_real_rows(client: httpx.AsyncClient) -> None:
    jwt, game, key = await game_with_key(client)
    await play(client, key, "a", 100, "win")
    await play(client, key, "b", 200, "loss")
    await register_player(client, key, "c")  # registered, never plays
    await start_session(client, key, "a")  # an active session
    await sql(
        "UPDATE game_sessions SET duration_seconds = 60 WHERE status='completed' "
        "AND player_id = (SELECT id FROM players WHERE external_id='a')"
    )
    await sql(
        "UPDATE game_sessions SET duration_seconds = 120 WHERE status='completed' "
        "AND player_id = (SELECT id FROM players WHERE external_id='b')"
    )

    overview = await _get(client, jwt, game["id"], "overview")
    assert overview["total_players"] == 3
    assert overview["total_sessions"] == 3 and overview["completed_sessions"] == 2
    assert overview["avg_session_duration_seconds"] == pytest.approx(90.0)
    assert overview["currently_active_players"] == 1
    assert overview["daily_active_players"] == 3 and overview["monthly_active_players"] == 3

    counted = await sql_count_events(game["id"])
    assert overview["total_events"] == counted > 0


async def sql_count_events(game_id: str) -> int:
    from tests.helpers import sql_all

    return (await sql_all("SELECT count(*) FROM events WHERE game_id = :g", g=game_id))[0][0]


# --- active players -----------------------------------------------------------------------


async def test_daily_and_monthly_active_players_use_rolling_windows(
    client: httpx.AsyncClient,
) -> None:
    jwt, game, key = await game_with_key(client)
    for name in ("today", "ten_days", "forty_days"):
        await play(client, key, name, 10)
    await shift_player("ten_days", 10)
    await shift_player("forty_days", 40)

    overview = await _get(client, jwt, game["id"], "overview")
    assert overview["daily_active_players"] == 1
    assert overview["monthly_active_players"] == 2  # the 40-day-old player is outside 30 days


async def test_period_is_compared_with_the_previous_period(client: httpx.AsyncClient) -> None:
    jwt, game, key = await game_with_key(client)
    await play(client, key, "now1", 10)
    await play(client, key, "now2", 10)
    await play(client, key, "old", 10)
    await shift_player("old", 10)  # falls in the previous 7-day window (days 7-14)

    overview = await _get(client, jwt, game["id"], "overview", "days=7")
    assert overview["current"]["active_players"] == 2
    assert overview["current"]["new_players"] == 2 and overview["current"]["sessions"] == 2
    assert overview["previous"]["active_players"] == 1
    assert overview["previous"]["new_players"] == 1 and overview["previous"]["sessions"] == 1
    assert overview["current"]["events"] > 0 and overview["previous"]["events"] > 0


# --- engagement trends -------------------------------------------------------------------------


async def test_engagement_series_is_daily_ordered_and_zero_filled(
    client: httpx.AsyncClient,
) -> None:
    jwt, game, key = await game_with_key(client)
    await play(client, key, "today", 10)
    await play(client, key, "two_days_ago", 10)
    await play(client, key, "two_days_ago_b", 10)
    await shift_player("two_days_ago", 2)
    await shift_player("two_days_ago_b", 2)

    data = await _get(client, jwt, game["id"], "engagement", "days=5")
    points = data["points"]
    today = datetime.now(UTC).date()
    assert [p["date"] for p in points] == [str(today - timedelta(days=i)) for i in (4, 3, 2, 1, 0)]

    by_date = {p["date"]: p for p in points}
    two = by_date[str(today - timedelta(days=2))]
    assert two["active_players"] == 2 and two["new_players"] == 2
    assert two["sessions_started"] == 2 and two["sessions_completed"] == 2
    assert by_date[str(today - timedelta(days=1))]["events"] == 0  # quiet day is a zero
    assert by_date[str(today)]["active_players"] == 1

    # The series adds up to the totals.
    assert sum(p["sessions_started"] for p in points) == 3
    overview = await _get(client, jwt, game["id"], "overview")
    assert sum(p["events"] for p in points) == overview["total_events"]


async def test_engagement_daily_average_duration(client: httpx.AsyncClient) -> None:
    jwt, game, key = await game_with_key(client)
    await play(client, key, "a", 1)
    await play(client, key, "b", 1)
    await sql(
        "UPDATE game_sessions SET duration_seconds = CASE WHEN player_id = "
        "(SELECT id FROM players WHERE external_id='a') THEN 30 ELSE 90 END"
    )
    today = (await _get(client, jwt, game["id"], "engagement", "days=2"))["points"][-1]
    assert today["avg_session_duration_seconds"] == pytest.approx(60.0)


# --- retention -------------------------------------------------------------------------------------


async def test_retention_counts_players_active_exactly_n_days_after_registering(
    client: httpx.AsyncClient,
) -> None:
    jwt, game, key = await game_with_key(client)
    for name in ("p1", "p2", "p3"):
        await register_player(client, key, name)
    # p1 and p2 registered 10 days ago; p3 two days ago.
    await sql(
        "UPDATE players SET created_at = now() - interval '10 days' WHERE external_id IN ('p1','p2')"
    )
    await sql("UPDATE players SET created_at = now() - interval '2 days' WHERE external_id = 'p3'")
    # Keep the registration events consistent with the backdated registration times.
    await sql(
        "UPDATE events SET occurred_at = p.created_at FROM players p "
        "WHERE events.player_id = p.id AND events.event_type = 'player_registered'"
    )
    # p1 came back exactly 1 day and 7 days after registering.
    for days_after in (1, 7):
        await sql(
            "INSERT INTO events (id, game_id, player_id, event_type, occurred_at) "
            "SELECT gen_random_uuid(), game_id, id, 'custom_return', created_at + make_interval(days => :d) "
            "FROM players WHERE external_id = 'p1'",
            d=days_after,
        )

    # p2 was active only just OUTSIDE the day-1 and day-7 windows: half a day before day 1,
    # and a day and a half after day 1, and just after day 7. None of these may count.
    for offset in ("12 hours", "2 days 12 hours", "8 days 12 hours"):
        await sql(
            "INSERT INTO events (id, game_id, player_id, event_type, occurred_at) "
            "SELECT gen_random_uuid(), game_id, id, 'custom_near_miss', created_at + CAST(:o AS interval) "
            "FROM players WHERE external_id = 'p2'",
            o=offset,
        )
    points = {p["day"]: p for p in (await _get(client, jwt, game["id"], "retention"))["points"]}
    assert (points[1]["eligible_players"], points[1]["retained_players"]) == (3, 1)
    assert points[1]["rate"] == pytest.approx(1 / 3, abs=0.001)
    assert (points[7]["eligible_players"], points[7]["retained_players"]) == (2, 1)
    assert points[7]["rate"] == 0.5
    assert points[30]["eligible_players"] == 0 and points[30]["rate"] is None  # not enough history


# --- score distribution ----------------------------------------------------------------------------


async def test_score_distribution_buckets_and_percentiles(client: httpx.AsyncClient) -> None:
    jwt, game, key = await game_with_key(client)
    for name, score in [("a", 100), ("b", 200), ("c", 300), ("d", 400), ("e", 1000)]:
        await play(client, key, name, score)

    data = await _get(client, jwt, game["id"], "scores", "buckets=3")
    assert data["completed_sessions"] == 5 and data["min"] == 100 and data["max"] == 1000
    assert data["average"] == pytest.approx(400.0)
    assert data["median"] == pytest.approx(300.0)
    assert data["p90"] == pytest.approx(760.0)
    buckets = data["buckets"]
    assert [b["count"] for b in buckets] == [4, 0, 1]
    assert buckets[0]["start"] == 100 and buckets[-1]["end"] >= 1000
    assert sum(b["count"] for b in buckets) == 5
    assert all(
        a["end"] + 1 == b["start"] for a, b in zip(buckets, buckets[1:], strict=False)
    )  # contiguous


async def test_score_distribution_with_identical_scores(client: httpx.AsyncClient) -> None:
    jwt, game, key = await game_with_key(client)
    await play(client, key, "a", 50)
    await play(client, key, "b", 50)
    data = await _get(client, jwt, game["id"], "scores")
    assert [(b["start"], b["end"], b["count"]) for b in data["buckets"]] == [(50, 50, 2)]


async def test_only_completed_sessions_count_toward_scores(client: httpx.AsyncClient) -> None:
    jwt, game, key = await game_with_key(client)
    await play(client, key, "a", 500)
    await register_player(client, key, "b")
    await start_session(client, key, "b")  # still active, score 0
    data = await _get(client, jwt, game["id"], "scores")
    assert data["completed_sessions"] == 1 and data["min"] == 500


# --- achievements ---------------------------------------------------------------------------------------


async def test_achievement_analytics(client: httpx.AsyncClient) -> None:
    jwt, game, key = await game_with_key(client)
    await play(client, key, "a", 2000, "win")  # first_game + high_scorer
    await play(client, key, "b", 10, "loss")  # first_game
    await shift_player("b", 3)

    data = await _get(client, jwt, game["id"], "achievements", "days=7")
    by_key = {a["key"]: a for a in data["achievements"]}
    assert by_key["first_game"]["unlock_count"] == 2 and by_key["first_game"]["unlock_rate"] == 1.0
    assert (
        by_key["high_scorer"]["unlock_count"] == 1 and by_key["high_scorer"]["unlock_rate"] == 0.5
    )
    assert by_key["champion"]["is_enabled"] is False and by_key["champion"]["unlock_count"] == 0
    assert data["total_unlocks"] == 3

    series = {d["date"]: d["count"] for d in data["unlocks_by_day"]}
    today = datetime.now(UTC).date()
    assert len(series) == 7
    assert series[str(today)] == 2 and series[str(today - timedelta(days=3))] == 1


# --- simulated data ----------------------------------------------------------------------------------------


async def test_simulated_data_can_be_excluded_everywhere(client: httpx.AsyncClient) -> None:
    jwt, game, key = await game_with_key(client)
    await play(client, key, "real", 100)
    await play(client, key, "fake", 900)
    await sql("UPDATE players SET is_simulated = true WHERE external_id = 'fake'")
    await sql(
        "UPDATE game_sessions SET is_simulated = true WHERE player_id = "
        "(SELECT id FROM players WHERE external_id = 'fake')"
    )
    await sql(
        "UPDATE events SET is_simulated = true WHERE player_id = "
        "(SELECT id FROM players WHERE external_id = 'fake')"
    )
    gid = game["id"]

    both = await _get(client, jwt, gid, "overview")
    real = await _get(client, jwt, gid, "overview", "include_simulated=false")
    assert both["total_players"] == 2 and real["total_players"] == 1
    assert real["total_sessions"] == 1 and real["include_simulated"] is False
    assert real["total_events"] < both["total_events"]

    scores = await _get(client, jwt, gid, "scores", "include_simulated=false")
    assert scores["completed_sessions"] == 1 and scores["max"] == 100
    engagement = await _get(client, jwt, gid, "engagement", "days=1&include_simulated=false")
    assert engagement["points"][0]["new_players"] == 1
    ach = await _get(client, jwt, gid, "achievements", "include_simulated=false")
    assert ach["total_unlocks"] == 1


# --- validation, access and isolation -------------------------------------------------------------------------


@pytest.mark.parametrize(
    "path, query",
    [
        ("overview", "days=0"),
        ("overview", "days=366"),
        ("engagement", "days=-1"),
        ("scores", "buckets=1"),
        ("scores", "buckets=31"),
        ("achievements", "days=abc"),
    ],
)
async def test_invalid_parameters_are_rejected(
    client: httpx.AsyncClient, path: str, query: str
) -> None:
    jwt, game, _ = await game_with_key(client)
    response = await client.get(f"{BASE.format(game['id'])}/{path}?{query}", headers=jwt)
    assert response.status_code == 422


async def test_analytics_require_authentication(client: httpx.AsyncClient) -> None:
    _, game, _ = await game_with_key(client)
    assert (await client.get(f"{BASE.format(game['id'])}/overview")).status_code == 401


async def test_analytics_are_isolated_between_tenants(client: httpx.AsyncClient) -> None:
    jwt_a, game_a, key_a = await game_with_key(client, "a@example.com", "Game A")
    jwt_b, game_b, key_b = await game_with_key(client, "b@example.com", "Game B")
    await play(client, key_a, "p1", 777)

    for path in ("overview", "engagement", "retention", "scores", "achievements"):
        foreign = await client.get(f"{BASE.format(game_a['id'])}/{path}", headers=jwt_b)
        assert foreign.status_code == 404, path
        missing = await client.get(f"{BASE.format(uuid.uuid4())}/{path}", headers=jwt_b)
        assert missing.status_code == 404

    # Game A's activity never shows up in game B's numbers.
    b_overview = await _get(client, jwt_b, game_b["id"], "overview")
    assert b_overview["total_players"] == 0 and b_overview["total_events"] == 0
    b_scores = await _get(client, jwt_b, game_b["id"], "scores")
    assert b_scores["completed_sessions"] == 0
    b_ach = await _get(client, jwt_b, game_b["id"], "achievements")
    assert b_ach["total_unlocks"] == 0


async def test_game_api_overview_is_scoped_to_the_key(client: httpx.AsyncClient) -> None:
    _, _, key_a = await game_with_key(client, "a@example.com", "Game A")
    _, _, key_b = await game_with_key(client, "b@example.com", "Game B")
    await play(client, key_a, "p1", 10)
    a = (await client.get("/api/v1/game/analytics/overview", headers=key_a)).json()
    b = (await client.get("/api/v1/game/analytics/overview", headers=key_b)).json()
    assert a["total_players"] == 1 and b["total_players"] == 0
    clamped = await client.get("/api/v1/game/analytics/overview?days=9999", headers=key_a)
    assert clamped.status_code == 200 and clamped.json()["period_days"] == 365
