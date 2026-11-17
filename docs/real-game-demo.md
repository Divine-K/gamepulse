# Real game demo: live chess from Lichess

The [Surfer example](integration-guide.md#7-try-it-end-to-end-the-surfer-example) plays a pretend game. This one connects GamePulse to a **real** game with real players, using a public API that needs no account and no key.

[Lichess](https://lichess.org) is a free, open-source chess site. It publishes the games its top players are playing right now on [lichess.org/tv](https://lichess.org/tv). The bridge in [`examples/lichess/bridge.py`](../examples/lichess/bridge.py) follows those live games and reports each one to the GamePulse Game API as it is played. The dashboard then shows a real game: real players, real sessions with real durations, and a live feed of what is happening on the board.

## Run it

1. Create a game in the dashboard (for example "Lichess Live") and an API key for it, as in the [integration guide](integration-guide.md#1-get-an-api-key).
2. Start the bridge, then open **Live Events** in the dashboard:

```bash
export GAMEPULSE_KEY=gp_xxxxxxxxxxxx_...
python examples/lichess/bridge.py --minutes 10                    # local API on :8000
python examples/lichess/bridge.py --minutes 10 --base-url https://your-api.example.com
```

It needs Python 3.10+ and nothing to install. Options: `--channels bullet,blitz,rapid` (any of Lichess's TV channels), `--minutes` (how long to run). Press Ctrl+C to stop early; open games are closed cleanly.

If you see `CERTIFICATE_VERIFY_FAILED` on a macOS Python from python.org, run its "Install Certificates.command" once (or use the project's virtualenv).

## What each Lichess fact becomes

Lichess has no concept of GamePulse, so the bridge chooses a mapping. It is deliberately simple and every number comes from the real game.

| In Lichess | In GamePulse |
|---|---|
| A TV game starts | Two players registered (`lichess:<username>`, with title and rating as metadata) and one **session per player**, because a player can have only one active session |
| The pieces still on the board | The player's **live score**: material points (queen 9, rook 5, bishop 3, knight 3, pawn 1; a full set is 39) times 10. It drops on every capture |
| A capture | A `custom_capture` event for the capturer, with the points taken, the move and the move number |
| The game starts and ends | `custom_game_started` and `custom_game_finished` events (status, winner, number of moves seen, speed, opening) |
| The result | The winner's session ends as a `win`, the other as a `loss`, a draw as a `draw`. A game still running when the bridge stops is closed without a result |
| A player's rating | A separate **`rating` leaderboard** (metric `category:rating`) |

Because the bridge joins games in progress, a game you join mid-way starts with whatever material is on the board at that moment, not 39.

## What it shows off

- **Live feed:** captures and score changes arrive on **Live Events** within a second of the move.
- **Sessions:** two per game, with real durations. In a test run, bullet games lasted under a minute to two minutes and blitz games nearly four.
- **Leaderboards:** by rating, wins, and material left on the board.
- **Custom events** with JSON payloads, and **achievements** unlocking as sessions end.
- **Recovery:** if an earlier run crashed and left a session open, the bridge closes it and starts fresh instead of failing.

## Being a good API citizen

- The bridge opens **one stream per channel** (three by default) and asks for the game result once per finished game. Use fewer channels with `--channels` if you want a lighter footprint.
- It identifies itself with a generic `User-Agent` and sends nothing about you.
- If Lichess answers `429` (slow down), it waits a full minute, as Lichess asks.
- Only public information is used: the username, title and rating of players shown on Lichess TV. Do not use it to build anything that identifies or contacts those players, and follow [Lichess's terms](https://lichess.org/terms-of-service) and [API guidelines](https://lichess.org/api).

## How it is tested

The backend suite runs the bridge against a **fake Lichess server on localhost** and a real GamePulse server, so the tests need no network and never touch Lichess. They cover a full game (captures, scores, win and loss, rating leaderboard), recovery from a leftover session, skipping a game with an anonymous player, and a bad API key. Each was checked by breaking the bridge on purpose and confirming a test failed.

## Another game?

The pattern is the same for any game with a read-only API: read it, translate what happens into players, sessions, scores and events, and send them through the [Game API](integration-guide.md). [`examples/clash_royale/bridge.py`](../examples/clash_royale/bridge.py) does this for Clash Royale: it imports a player's recent battles (needs a free developer key tied to your IP address, and is tested against a fake API only, not the live one). Other good candidates with free public data include Chess.com (finished games by username) and Lichess's own game exports.
