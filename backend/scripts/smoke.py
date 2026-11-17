"""Smoke test for a running GamePulse stack (used locally and in CI against the Docker build).

    python scripts/smoke.py http://localhost:8080
    python scripts/smoke.py https://api.example.com --api-only   # API deployed without the dashboard

It talks to the public entry point only, exactly like a real client: the dashboard, the REST API and
the live WebSocket. Exits non-zero on the first failure.
"""

import asyncio
import json
import sys
import uuid

import httpx
from websockets.asyncio.client import connect

_ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
BASE = (_ARGS[0] if _ARGS else "http://localhost:8080").rstrip("/")
API_ONLY = "--api-only" in sys.argv


def check(condition: bool, message: str) -> None:
    print(("ok   " if condition else "FAIL ") + message)
    if not condition:
        sys.exit(1)


async def main() -> None:
    async with httpx.AsyncClient(base_url=BASE, timeout=20) as http:
        if not API_ONLY:
            page = await http.get("/")
            check(
                page.status_code == 200 and '<div id="root">' in page.text,
                "dashboard HTML is served",
            )
            csp = page.headers.get("content-security-policy", "")
            check(
                "script-src 'self'" in csp and "frame-ancestors 'none'" in csp,
                "dashboard sends a strict CSP",
            )
            check(
                page.headers.get("x-content-type-options") == "nosniff", "dashboard sends nosniff"
            )
            check(
                "server" not in {k.lower() for k in page.headers}
                or "nginx/" not in page.headers.get("server", ""),
                "server version is hidden",
            )

            spa = await http.get("/players/some-id")
            check(
                spa.status_code == 200 and '<div id="root">' in spa.text,
                "unknown paths fall back to the single-page app",
            )

        health = await http.get("/health")
        check(health.json() == {"status": "ok"}, "/health is proxied to the API")
        ready = await http.get("/api/v1/health/ready")
        check(
            ready.json()["checks"] == {"postgres": "ok", "redis": "ok"},
            "API reaches PostgreSQL and Redis",
        )
        check(
            ready.headers.get("x-content-type-options") == "nosniff",
            "API responses carry security headers",
        )
        check(ready.headers.get("cache-control") == "no-store", "API JSON is not cacheable")

        email = f"smoke-{uuid.uuid4().hex[:8]}@example.com"
        reg = await http.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "smoke-test-pass", "display_name": "Smoke"},
        )
        check(reg.status_code == 201, "register a developer")
        login = await http.post(
            "/api/v1/auth/login", json={"email": email, "password": "smoke-test-pass"}
        )
        jwt = {"Authorization": f"Bearer {login.json()['access_token']}"}
        game = (await http.post("/api/v1/games", json={"name": "Smoke Game"}, headers=jwt)).json()
        key = (
            await http.post(
                f"/api/v1/games/{game['id']}/api-keys", json={"name": "smoke"}, headers=jwt
            )
        ).json()["key"]
        gk = {"X-API-Key": key}
        check(
            (await http.get("/api/v1/game/me", headers=gk)).json()["id"] == game["id"],
            "API key authenticates its game",
        )

        ws_url = BASE.replace("http", "ws", 1) + f"/api/v1/ws/games/{game['id']}"
        async with connect(ws_url) as ws:
            await ws.send(json.dumps({"type": "auth", "token": jwt["Authorization"].split()[1]}))
            ready_msg = json.loads(await asyncio.wait_for(ws.recv(), 5))
            check(ready_msg["type"] == "ready", "WebSocket authenticates through the proxy")

            await http.post(
                "/api/v1/game/players",
                json={"external_id": "smoke-1", "username": "Smoke"},
                headers=gk,
            )
            session = (
                await http.post(
                    "/api/v1/game/sessions", json={"player_external_id": "smoke-1"}, headers=gk
                )
            ).json()
            seen = []
            async with asyncio.timeout(6):
                while "session.started" not in seen:
                    seen.append(json.loads(await ws.recv())["type"])
            check(
                "player.registered" in seen and "session.started" in seen,
                "live events are pushed over the WebSocket",
            )

        ended = await http.post(
            f"/api/v1/game/sessions/{session['id']}/end",
            json={"score": 1500, "result": "win"},
            headers=gk,
        )
        check(
            ended.status_code == 200 and len(ended.json()["unlocked_achievements"]) > 0,
            "ending a session unlocks achievements",
        )
        board = (await http.get("/api/v1/game/leaderboards/total_score", headers=gk)).json()
        check(board["items"][0]["value"] == 1500, "leaderboard reflects the score")
        overview = (
            await http.get(f"/api/v1/games/{game['id']}/analytics/overview", headers=jwt)
        ).json()
        check(
            overview["total_players"] == 1 and overview["total_sessions"] == 1,
            "analytics are computed from real records",
        )
        check(
            (
                await http.get(
                    f"/api/v1/games/{game['id']}/players", headers={"Authorization": "Bearer bad"}
                )
            ).status_code
            == 401,
            "invalid tokens are rejected",
        )
    print("\nSMOKE TEST PASSED")


asyncio.run(main())
