"""Mirror live Lichess games into GamePulse.

Lichess (a free, open-source chess site) publishes the games its top players are playing right now,
with no account or API key. This bridge follows those live games and reports each one to the
GamePulse Game API as it happens, so the dashboard shows a real game with real players:

  * each game becomes two sessions, one per player (a player can only have one active session)
  * a player's live score is the material they still have on the board (queen 9, rook 5,
    bishop 3, knight 3, pawn 1; a full set is 39), ten times over, and it drops on every capture
  * every capture is a `custom_capture` event, the start and end of a game are `custom_game_*`
    events, and the winner's session ends as a win
  * each player's rating goes to a separate `rating` leaderboard (metric `category:rating`)

    export GAMEPULSE_KEY=gp_...        # an API key for one of your games
    python examples/lichess/bridge.py --minutes 10

The games and players are public on lichess.org/tv; only usernames, titles and ratings are used.
Be kind to Lichess: the bridge opens one stream per channel (three by default) and backs off for a
minute if it is told to slow down.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterator
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "surfer"))
from gamepulse_client import GamePulse, GamePulseError  # noqa: E402

LICHESS = "https://lichess.org"
USER_AGENT = "game-event-bridge/1.0"  # generic on purpose: it says nothing about who runs it
PIECE_VALUES = {"p": 1, "n": 3, "b": 3, "r": 5, "q": 9}
SCORE_PER_POINT = 10
_print_lock = threading.Lock()


def say(message: str) -> None:
    with _print_lock:
        print(message, flush=True)


# --- pure helpers --------------------------------------------------------------------------------


def material(fen: str) -> tuple[int, int]:
    """Material points (white, black) from a FEN string. Kings do not count."""
    placement = fen.split(" ")[0].split("[")[0]  # drop crazyhouse pockets
    white = black = 0
    for char in placement:
        value = PIECE_VALUES.get(char.lower())
        if value:
            if char.isupper():
                white += value
            else:
                black += value
    return white, black


def outcome(game: dict) -> str | None:
    """Who won: "white", "black", "draw", or None when there is no result (running or aborted)."""
    status = game.get("status", "")
    if winner := game.get("winner"):
        return winner
    if status in {"draw", "stalemate"}:
        return "draw"
    return None


# --- Lichess access ------------------------------------------------------------------------------


class LichessError(Exception):
    pass


def lichess_request(base: str, path: str, accept: str) -> urllib.request.Request:
    return urllib.request.Request(
        f"{base}{path}", headers={"Accept": accept, "User-Agent": USER_AGENT}
    )


def lichess_json(base: str, path: str) -> dict:
    try:
        with urllib.request.urlopen(
            lichess_request(base, path, "application/json"), timeout=30
        ) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as error:
        raise LichessError(f"{error.code} for {path}") from None


def lichess_stream(base: str, path: str, timeout: float = 20.0) -> Iterator[dict]:
    """Yield the JSON objects of a newline-delimited stream until it closes."""
    request = lichess_request(base, path, "application/x-ndjson")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        for raw in response:
            line = raw.strip()
            if line:
                yield json.loads(line)


# --- GamePulse access ----------------------------------------------------------------------------


class Client(GamePulse):
    def active_session_id(self, external_id: str) -> str | None:
        """The player's active session, if one is left over from an earlier run."""
        quoted = urllib.parse.quote(external_id, safe="")
        page = self._request("GET", f"/players/{quoted}/sessions?limit=5")
        for session in page["items"]:
            if session["status"] == "active":
                return session["id"]
        return None


class Stats:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.games = self.captures = self.finished = self.skipped = 0

    def add(self, name: str, amount: int = 1) -> None:
        with self.lock:
            setattr(self, name, getattr(self, name) + amount)


class Side:
    """One player in one live game."""

    def __init__(self, colour: str, info: dict) -> None:
        user = info["user"]
        self.colour = colour
        self.external_id = f"lichess:{user['id']}"
        self.name = user["name"]
        self.title = user.get("title")
        self.rating = info.get("rating")
        self.session_id = ""
        self.material = 39


class LiveGame:
    """Reports one Lichess game to GamePulse from the first position to the result."""

    def __init__(
        self, api: Client, lichess: str, channel: str, featured: dict, stats: Stats
    ) -> None:
        self.api, self.lichess, self.channel, self.stats = api, lichess, channel, stats
        self.game_id = featured["id"]
        self.sides: dict[str, Side] = {}
        for entry in featured["players"]:
            if "user" not in entry:
                raise LichessError("a player is anonymous")  # nothing to attribute the game to
            self.sides[entry["color"]] = Side(entry["color"], entry)
        if set(self.sides) != {"white", "black"}:
            raise LichessError("expected two players")
        self.plies = 0
        self.last_fen = featured.get("fen", "")
        self.started = time.monotonic()

    @property
    def label(self) -> str:
        w, b = self.sides["white"], self.sides["black"]
        return f"[{self.channel}] {w.name} ({w.rating}) vs {b.name} ({b.rating})"

    def start(self) -> None:
        for side in self.sides.values():
            meta = {"lichess_title": side.title, "lichess_rating": side.rating}
            self.api.register_player(side.external_id, side.name, meta)
            side.session_id = self._start_session(side)
            self.api.send_event(
                "custom_game_started",
                side.external_id,
                side.session_id,
                {
                    "game_id": self.game_id,
                    "channel": self.channel,
                    "colour": side.colour,
                    "rating": side.rating,
                    "opponent_rating": self.other(side).rating,
                },
            )
            if side.rating:
                self.api.submit_score(side.external_id, side.rating, category="rating")
        if self.last_fen:
            self.on_position(self.last_fen, move=None, first=True)
        self.stats.add("games")
        say(f"{self.label}  started")

    def other(self, side: Side) -> Side:
        return self.sides["black" if side.colour == "white" else "white"]

    def _start_session(self, side: Side) -> str:
        try:
            return self.api.start_session(side.external_id)["id"]
        except GamePulseError as error:
            if error.code != "session_already_active":
                raise
            leftover = self.api.active_session_id(side.external_id)
            if leftover:  # a crashed earlier run left it open: close it, then start fresh
                self.api.end_session(leftover)
            return self.api.start_session(side.external_id)["id"]

    def on_position(self, fen: str, move: str | None, first: bool = False) -> None:
        if not first:
            self.plies += 1
        white, black = material(fen)
        now = {"white": white, "black": black}
        for colour, side in self.sides.items():
            if now[colour] != side.material or first:
                lost = side.material - now[colour]
                side.material = now[colour]
                self.api.submit_score(
                    side.external_id, now[colour] * SCORE_PER_POINT, session_id=side.session_id
                )
                if lost > 0 and not first:
                    capturer = self.other(side)
                    self.api.send_event(
                        "custom_capture",
                        capturer.external_id,
                        capturer.session_id,
                        {"points": lost, "move": move, "ply": self.plies, "game_id": self.game_id},
                    )
                    self.stats.add("captures")
                    say(f"{self.label}  {capturer.name} captures {lost} point(s)")
        self.last_fen = fen

    def finish(self) -> None:
        """Ask Lichess how the game ended, then close both sessions."""
        try:
            game = lichess_json(
                self.lichess, f"/game/export/{self.game_id}?moves=false&clocks=false&opening=true"
            )
        except (LichessError, urllib.error.URLError, TimeoutError, OSError):
            game = {}
        won = outcome(game)
        opening = (game.get("opening") or {}).get("name")
        for colour, side in self.sides.items():
            if won in (None, "draw"):
                result = "draw" if won == "draw" else None
            else:
                result = "win" if won == colour else "loss"
            self.api.send_event(
                "custom_game_finished",
                side.external_id,
                side.session_id,
                {
                    "game_id": self.game_id,
                    "status": game.get("status", "unknown"),
                    "winner": won,
                    "plies": self.plies,
                    "speed": game.get("speed"),
                    "opening": opening,
                },
            )
            self.api.end_session(
                side.session_id, score=side.material * SCORE_PER_POINT, result=result
            )
        self.stats.add("finished")
        say(f"{self.label}  finished: {game.get('status', 'left running')}, winner {won or '-'}")


# --- one thread per Lichess TV channel -----------------------------------------------------------


def watch_channel(
    channel: str,
    api: Client,
    lichess: str,
    stats: Stats,
    stop: threading.Event,
    once: bool,
) -> None:
    game: LiveGame | None = None

    def close_game() -> None:
        nonlocal game
        if game:
            try:
                game.finish()
            except GamePulseError as error:
                say(f"[{channel}] could not close game: {error}")
            game = None

    while not stop.is_set():
        try:
            for event in lichess_stream(lichess, f"/api/tv/{channel}/feed"):
                if stop.is_set():
                    break
                kind, data = event.get("t"), event.get("d", {})
                if kind == "featured" and game and data.get("id") == game.game_id:
                    continue  # the stream reconnected and repeated the game we already follow
                if kind == "featured":
                    close_game()
                    try:
                        game = LiveGame(api, lichess, channel, data, stats)
                        game.start()
                    except LichessError as reason:
                        stats.add("skipped")
                        say(f"[{channel}] skipping game {data.get('id')}: {reason}")
                        game = None
                elif kind == "fen" and game:
                    game.on_position(data["fen"], data.get("lm"))
        except urllib.error.HTTPError as error:
            wait = 60 if error.code == 429 else 5
            say(f"[{channel}] Lichess answered {error.code}; waiting {wait}s")
            stop.wait(wait)
        except TimeoutError:
            pass  # a quiet stretch (a slow game): reconnect and carry on
        except (urllib.error.URLError, OSError) as error:
            say(f"[{channel}] stream interrupted ({error}); reconnecting")
            stop.wait(3)
        except GamePulseError as error:
            say(f"[{channel}] GamePulse error: {error}")
            stop.wait(3)
        if once:
            break
        stop.wait(1)  # never reconnect in a tight loop
    close_game()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--base-url", default=os.getenv("GAMEPULSE_URL", "http://localhost:8000"))
    parser.add_argument("--api-key", default=os.getenv("GAMEPULSE_KEY"))
    parser.add_argument("--lichess-url", default=LICHESS, help=argparse.SUPPRESS)
    parser.add_argument(
        "--channels",
        default="bullet,blitz,rapid",
        help="Lichess TV channels to follow, comma separated (default: %(default)s)",
    )
    parser.add_argument("--minutes", type=float, default=10, help="how long to run")
    parser.add_argument("--once", action="store_true", help="stop when each stream closes")
    args = parser.parse_args()
    if not args.api_key:
        parser.error("set GAMEPULSE_KEY or pass --api-key")

    api = Client(args.base_url, args.api_key)
    try:
        game = api.whoami()
    except GamePulseError as error:
        print(f"GamePulse error: {error}", file=sys.stderr)
        return 1
    channels = [c.strip() for c in args.channels.split(",") if c.strip()]
    say(f"Following Lichess TV ({', '.join(channels)}) into {game['name']!r} on {args.base_url}")

    stats, stop = Stats(), threading.Event()
    threads = [
        threading.Thread(
            target=watch_channel,
            args=(channel, api, args.lichess_url, stats, stop, args.once),
            daemon=True,
        )
        for channel in channels
    ]
    for thread in threads:
        thread.start()
    deadline = time.monotonic() + args.minutes * 60
    try:
        while time.monotonic() < deadline and any(t.is_alive() for t in threads):
            time.sleep(0.5)
    except KeyboardInterrupt:
        say("Stopping...")
    stop.set()
    for thread in threads:
        thread.join(timeout=60)  # each closes its open game before exiting
    say(
        f"\nDone: {stats.games} games followed, {stats.finished} finished, "
        f"{stats.captures} captures reported, {stats.skipped} skipped."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
