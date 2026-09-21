"""Chess.com / Lichess API pulls — fetch a player's recent games by username.

Both public APIs are unauthenticated, read-only, public-data endpoints — no
OAuth/login flow is built or needed. Every network call is wrapped in
try/except per Rules.md: a failed request is logged clearly and never
propagates a raw exception past this module uncaught.

fetch_last_n_games() is the primary, product-facing entry point (per the
2026-09-21 scope change logged in Memory.md: single-input dashboard/CLI —
Chess.com username + game count, no manual PGN upload, no source selection).
fetch_chess_com_games()/fetch_lichess_games()/fetch_games() remain as
lower-level building blocks (fetch_last_n_games reuses fetch_chess_com_games'
per-month helper) and as still-available, deliberately-not-removed
Lichess support for future use.
"""

import logging
import time

import chess.pgn
import requests

from src.ingestion.parse_pgn import parse_pgn_string

logger = logging.getLogger(__name__)

_REQUEST_TIMEOUT_SECONDS = 15
_USER_AGENT = "ChessMentorNLP/0.1 (course project; contact via GitHub)"
DEFAULT_N_GAMES = 50


class ChessComUsernameNotFoundError(Exception):
    """Raised when the Chess.com API confirms the given username does not exist."""


class ChessComNoPublicGamesError(Exception):
    """Raised when a username exists but has no public games available (e.g. a
    private or genuinely empty profile — the archives list came back empty)."""


class ChessComAPIError(Exception):
    """Raised when a Chess.com API request fails after one retry (network error,
    rate limit, timeout, or any non-404 HTTP error)."""


def _get_with_retry(url: str, *, params: dict | None = None) -> requests.Response:
    """Input shape: url str, params optional dict (query params).
    Output shape: requests.Response (a successful, status-checked response).

    Purpose: shared GET-with-one-retry helper for all Chess.com API calls, per
    the required request behavior: "retry once, then fail gracefully". Raises
    ChessComAPIError with a clear message if both attempts fail; never lets a
    raw requests exception escape this function.
    """
    headers = {"User-Agent": _USER_AGENT}
    last_error: Exception | None = None
    for attempt in (1, 2):
        try:
            response = requests.get(url, headers=headers, params=params, timeout=_REQUEST_TIMEOUT_SECONDS)
        except requests.exceptions.RequestException as exc:
            last_error = exc
            logger.warning("Chess.com request to '%s' failed (attempt %d/2): %s", url, attempt, exc)
            if attempt == 1:
                time.sleep(1)
            continue

        if response.status_code == 404:
            # Let the caller decide what a 404 means in context (username-not-found
            # vs. some other missing resource) rather than treating it as a generic
            # retry-worthy failure.
            return response
        if response.ok:
            return response

        last_error = requests.exceptions.HTTPError(
            f"Chess.com API returned HTTP {response.status_code} for '{url}'"
        )
        logger.warning("Chess.com request to '%s' failed (attempt %d/2): %s", url, attempt, last_error)
        if attempt == 1:
            time.sleep(1)

    raise ChessComAPIError(
        f"Chess.com API request to '{url}' failed after 1 retry: {last_error}"
    )


def fetch_last_n_games(username: str, n: int = DEFAULT_N_GAMES) -> list[chess.pgn.Game]:
    """Input shape: username str (Chess.com handle), n int (how many of the player's
    most recent games to fetch; default 50).
    Output shape: list[chess.pgn.Game], the player's `n` most recent public games
    (or fewer if the account has fewer than `n` total), sorted chronologically
    oldest -> newest, ready to feed straight into annotation.

    Purpose: the single ingestion entry point for the current single-input
    (username + game count) product design. Walks the player's monthly archive
    list newest-to-oldest, pulling whole months until at least `n` games have
    been collected (or archives run out), then trims to exactly the most recent
    `n`. Raises ChessComUsernameNotFoundError if the username doesn't exist,
    ChessComNoPublicGamesError if it exists but has no public games, and
    ChessComAPIError if a request ultimately fails after one retry — callers
    (CLI/dashboard) are expected to catch these and show a clear message,
    never a raw traceback (Rules.md §2).
    """
    archives_url = f"https://api.chess.com/pub/player/{username}/games/archives"
    response = _get_with_retry(archives_url)

    if response.status_code == 404:
        raise ChessComUsernameNotFoundError(f"Chess.com username '{username}' was not found.")

    try:
        archive_urls = response.json().get("archives", [])
    except ValueError as exc:
        raise ChessComAPIError(f"Chess.com archive list returned invalid JSON for '{username}': {exc}") from exc

    if not archive_urls:
        raise ChessComNoPublicGamesError(
            f"'{username}' has no public games available (private or empty profile)."
        )

    games_newest_first: list[chess.pgn.Game] = []
    for archive_url in reversed(archive_urls):
        if len(games_newest_first) >= n:
            break
        try:
            month_response = _get_with_retry(archive_url)
        except ChessComAPIError as exc:
            logger.warning("Skipping archive '%s' after retry failure: %s", archive_url, exc)
            continue

        try:
            month_entries = month_response.json().get("games", [])
        except ValueError as exc:
            logger.warning("Skipping archive '%s' (invalid JSON): %s", archive_url, exc)
            continue

        month_games: list[chess.pgn.Game] = []
        for entry in month_entries:  # chronological oldest -> newest within a month
            pgn_text = entry.get("pgn")
            if not pgn_text:
                logger.warning("Skipping Chess.com game with no PGN field in archive '%s'", archive_url)
                continue
            month_games.extend(parse_pgn_string(pgn_text))

        games_newest_first.extend(reversed(month_games))  # newest game of the month first

    games_newest_first = games_newest_first[:n]
    games = list(reversed(games_newest_first))  # oldest -> newest, matching the pipeline's expectation

    if len(games) < n:
        logger.info(
            "'%s' has only %d public game(s) available (requested %d); analyzing all of them.",
            username, len(games), n,
        )
    return games


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
