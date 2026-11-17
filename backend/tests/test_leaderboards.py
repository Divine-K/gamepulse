import httpx
from sqlalchemy import text

from app.core.database import get_engine
from tests.helpers import game_with_key, play, register_player


def _board(response: httpx.Response) -> list[tuple[int, str, int]]:
    return [(e["rank"], e["player"]["username"], e["value"]) for e in response.json()["items"]]


async def _seed(client: httpx.AsyncClient, key: dict) -> None:
    await play(client, key, "ada", 500, "win")
    await play(client, key, "bob", 300, "loss")
    await play(client, key, "cyd", 300, "win")
    await play(client, key, "dee", 100, "win")
    await play(client, key, "ada", 200, "win")  # ada: total 700, best 500, 2 wins


async def test_total_score_ranking_with_ties_sharing_a_rank(client: httpx.AsyncClient) -> None:
    _, _, key = await game_with_key(client)
    await _seed(client, key)
    board = await client.get("/api/v1/game/leaderboards/total_score", headers=key)
    ranks = _board(board)
    assert ranks[0] == (1, "ada", 700)
    # bob and cyd both have 300 -> both rank 2, dee is 4 (competition ranking)
    assert sorted(ranks[1:3]) == [(2, "bob", 300), (2, "cyd", 300)]
    assert ranks[3] == (4, "dee", 100)
    body = board.json()
    assert body["metric"] == "total_score" and body["total"] == 4


async def test_other_metrics(client: httpx.AsyncClient) -> None:
    _, _, key = await game_with_key(client)
    await _seed(client, key)
    best = await client.get("/api/v1/game/leaderboards/best_score", headers=key)
    assert _board(best)[0] == (1, "ada", 500)
    wins = await client.get("/api/v1/game/leaderboards/wins", headers=key)
    assert _board(wins)[0] == (1, "ada", 2)
    # players with a zero value are not ranked: bob has no wins
    assert "bob" not in [name for _, name, _ in _board(wins)]


async def test_leaderboard_entries_include_stats(client: httpx.AsyncClient) -> None:
    _, _, key = await game_with_key(client)
    await _seed(client, key)
    top = (await client.get("/api/v1/game/leaderboards/total_score", headers=key)).json()["items"][
        0
    ]
    assert top["stats"]["wins"] == 2 and top["stats"]["completed_sessions"] == 2
    assert top["stats"]["achievements_count"] >= 1  # "First Game" etc.


async def test_pagination_order_search_and_min_value(client: httpx.AsyncClient) -> None:
    _, _, key = await game_with_key(client)
    await _seed(client, key)
    base = "/api/v1/game/leaderboards/total_score"

    page2 = await client.get(f"{base}?limit=2&offset=2", headers=key)
    assert page2.json()["total"] == 4 and len(page2.json()["items"]) == 2

    asc = _board(await client.get(f"{base}?order=asc", headers=key))
    assert asc[0] == (4, "dee", 100) and asc[-1] == (1, "ada", 700)

    # Searching keeps the global rank: filtering to "dee" still shows rank 4.
    search = _board(await client.get(f"{base}?q=dee", headers=key))
    assert search == [(4, "dee", 100)]
    assert _board(await client.get(f"{base}?min_value=300", headers=key)) != []
    assert len(_board(await client.get(f"{base}?min_value=300", headers=key))) == 3
    assert (await client.get(f"{base}?limit=500", headers=key)).status_code == 422


async def test_player_rank_endpoint(client: httpx.AsyncClient) -> None:
    _, _, key = await game_with_key(client)
    await _seed(client, key)
    rank = await client.get("/api/v1/game/leaderboards/total_score/players/dee", headers=key)
    assert rank.status_code == 200
    assert rank.json()["rank"] == 4 and rank.json()["value"] == 100

    await register_player(client, key, "newbie")
    unranked = await client.get("/api/v1/game/leaderboards/total_score/players/newbie", headers=key)
    assert unranked.status_code == 404 and unranked.json()["error"]["code"] == "player_not_ranked"
    ghost = await client.get("/api/v1/game/leaderboards/total_score/players/ghost", headers=key)
    assert ghost.status_code == 404


async def test_custom_category_metric_uses_the_best_value_and_periods(
    client: httpx.AsyncClient,
) -> None:
    _, _, key = await game_with_key(client)
    await register_player(client, key, "p1", username="p1")
    await register_player(client, key, "p2", username="p2")
    for player, value in [("p1", 10), ("p1", 90), ("p2", 50)]:
        await client.post(
            "/api/v1/game/scores",
            json={"player_external_id": player, "value": value, "category": "coins"},
            headers=key,
        )
    board = _board(await client.get("/api/v1/game/leaderboards/category:coins", headers=key))
    assert board == [(1, "p1", 90), (2, "p2", 50)]  # best value per player

    # Age p1's entries beyond a week: weekly shows only p2, all-time still shows both.
    async with get_engine().begin() as conn:
        await conn.execute(
            text(
                "UPDATE score_entries SET created_at = now() - interval '10 days' "
                "WHERE category='coins' AND value IN (10, 90)"
            )
        )
    weekly = _board(
        await client.get("/api/v1/game/leaderboards/category:coins?period=weekly", headers=key)
    )
    assert weekly == [(1, "p2", 50)]
    monthly = _board(
        await client.get("/api/v1/game/leaderboards/category:coins?period=monthly", headers=key)
    )
    assert len(monthly) == 2


async def test_unknown_metric_and_unsupported_period(client: httpx.AsyncClient) -> None:
    _, _, key = await game_with_key(client)
    unknown = await client.get("/api/v1/game/leaderboards/popularity", headers=key)
    assert unknown.status_code == 422 and unknown.json()["error"]["code"] == "unknown_metric"
    bad_cat = await client.get("/api/v1/game/leaderboards/category:Bad Name!", headers=key)
    assert bad_cat.status_code == 422
    period = await client.get("/api/v1/game/leaderboards/total_score?period=weekly", headers=key)
    assert period.status_code == 422 and period.json()["error"]["code"] == "period_not_supported"
    empty = await client.get("/api/v1/game/leaderboards/category:nothing_yet", headers=key)
    assert empty.status_code == 200 and empty.json()["items"] == []


async def test_dashboard_leaderboard_matches_game_api(client: httpx.AsyncClient) -> None:
    jwt, game, key = await game_with_key(client)
    await _seed(client, key)
    via_key = (await client.get("/api/v1/game/leaderboards/total_score", headers=key)).json()
    via_jwt = (
        await client.get(f"/api/v1/games/{game['id']}/leaderboards/total_score", headers=jwt)
    ).json()
    assert via_key == via_jwt


async def test_leaderboards_are_isolated_between_games(client: httpx.AsyncClient) -> None:
    jwt_a, game_a, key_a = await game_with_key(client, "a@example.com", "Game A")
    jwt_b, game_b, key_b = await game_with_key(client, "b@example.com", "Game B")
    await play(client, key_a, "shared", 999, "win")
    await play(client, key_b, "shared", 1, "loss")

    a = _board(await client.get("/api/v1/game/leaderboards/total_score", headers=key_a))
    b = _board(await client.get("/api/v1/game/leaderboards/total_score", headers=key_b))
    assert a == [(1, "shared", 999)] and b == [(1, "shared", 1)]

    foreign = await client.get(
        f"/api/v1/games/{game_a['id']}/leaderboards/total_score", headers=jwt_b
    )
    assert foreign.status_code == 404
