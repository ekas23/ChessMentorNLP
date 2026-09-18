"""Chess.com / Lichess API pulls — fetch a player's recent games by username.

Both public APIs are unauthenticated for read access. Every network call is
wrapped in try/except per Rules.md: a failed request is logged clearly and
returns an empty list rather than crashing the pipeline.
"""

import logging

import chess.pgn
import requests

from src.ingestion.parse_pgn import parse_pgn_string

logger = logging.getLogger(__name__)

_REQUEST_TIMEOUT_SECONDS = 15
_USER_AGENT = "ChessMentorNLP/0.1 (course project; contact via GitHub)"


def fetch_chess_com_games(username: str, max_games: int = 20) -> list[chess.pgn.Game]:
    """Input shape: username: str (Chess.com handle), max_games: int (cap on games returned).
    Output shape: list[chess.pgn.Game], most recent games first, length <= max_games.

    Purpose: pull a player's most recent games from the Chess.com public API.
    Walks the player's monthly archive list newest-first, downloading archives
    and accumulating games until max_games is reached. Any archive that fails
    to fetch or parse is logged and skipped rather than aborting the whole pull.
    """
    headers = {"User-Agent": _USER_AGENT}
    archives_url = f"https://api.chess.com/pub/player/{username}/games/archives"

    try:
        resp = requests.get(archives_url, headers=headers, timeout=_REQUEST_TIMEOUT_SECONDS)
        resp.raise_for_status()
        archive_urls = resp.json().get("archives", [])
    except requests.exceptions.RequestException as exc:
        logger.error("Chess.com archive list request failed for user '%s': %s", username, exc)
        return []
    except ValueError as exc:
        logger.error("Chess.com archive list returned invalid JSON for user '%s': %s", username, exc)
        return []

    games: list[chess.pgn.Game] = []
    for archive_url in reversed(archive_urls):
        if len(games) >= max_games:
            break
        try:
            resp = requests.get(archive_url, headers=headers, timeout=_REQUEST_TIMEOUT_SECONDS)
            resp.raise_for_status()
            month_games = resp.json().get("games", [])
        except requests.exceptions.RequestException as exc:
            logger.warning("Skipping archive '%s' (request failed): %s", archive_url, exc)
            continue
        except ValueError as exc:
            logger.warning("Skipping archive '%s' (invalid JSON): %s", archive_url, exc)
            continue

        for entry in reversed(month_games):
            if len(games) >= max_games:
                break
            pgn_text = entry.get("pgn")
            if not pgn_text:
                logger.warning("Skipping Chess.com game with no PGN field in archive '%s'", archive_url)
                continue
            parsed = parse_pgn_string(pgn_text)
            games.extend(parsed)

    return games[:max_games]


def fetch_lichess_games(username: str, max_games: int = 20) -> list[chess.pgn.Game]:
    """Input shape: username: str (Lichess handle), max_games: int (cap on games returned).
    Output shape: list[chess.pgn.Game], most recent games first, length <= max_games.

    Purpose: pull a player's most recent games from the Lichess public API, which
    streams them back as a single PGN blob (newest first) via the `max` query param.
    """
    url = f"https://lichess.org/api/games/user/{username}"
    headers = {"User-Agent": _USER_AGENT, "Accept": "application/x-chess-pgn"}
    params = {"max": max_games, "pgnInJson": "false"}

    try:
        resp = requests.get(url, headers=headers, params=params, timeout=_REQUEST_TIMEOUT_SECONDS)
        resp.raise_for_status()
    except requests.exceptions.RequestException as exc:
        logger.error("Lichess games request failed for user '%s': %s", username, exc)
        return []

    games = parse_pgn_string(resp.text)
    return games[:max_games]


def fetch_games(username: str, source: str = "chess.com", max_games: int = 20) -> list[chess.pgn.Game]:
    """Input shape: username: str, source: 'chess.com' | 'lichess', max_games: int.
    Output shape: list[chess.pgn.Game], most recent games first, length <= max_games.

    Purpose: single entry point for API-based ingestion, dispatching to the
    matching per-platform fetch function.
    """
    if source == "chess.com":
        return fetch_chess_com_games(username, max_games=max_games)
    if source == "lichess":
        return fetch_lichess_games(username, max_games=max_games)
    raise ValueError(f"Unknown source '{source}'; expected 'chess.com' or 'lichess'")
