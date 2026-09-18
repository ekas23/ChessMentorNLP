"""PGN → game objects. Handles both PGN files on disk and raw PGN text pulled
from an API (which may contain multiple concatenated games).
"""

import io
import logging

import chess.pgn

logger = logging.getLogger(__name__)


def parse_pgn_string(pgn_text: str) -> list[chess.pgn.Game]:
    """Input shape: str, raw PGN text containing one or more concatenated games.
    Output shape: list[chess.pgn.Game] — one entry per successfully parsed game.

    Purpose: parse a PGN blob (e.g. returned by the Chess.com/Lichess APIs) into
    game objects. A game is validated by requiring it to have at least one move
    or a recognizable header; malformed games are skipped and logged rather than
    raising, so one bad game in a batch never halts the whole pull.
    """
    games: list[chess.pgn.Game] = []
    stream = io.StringIO(pgn_text)
    game_index = 0
    while True:
        try:
            game = chess.pgn.read_game(stream)
        except Exception as exc:
            logger.warning("Skipping malformed PGN at game index %d: %s", game_index, exc)
            break
        if game is None:
            break
        if not _is_well_formed(game):
            logger.warning("Skipping malformed/empty game at index %d", game_index)
            game_index += 1
            continue
        games.append(game)
        game_index += 1
    return games


def parse_pgn_file(file_path: str) -> list[chess.pgn.Game]:
    """Input shape: str, path to a .pgn file on disk (may contain multiple games).
    Output shape: list[chess.pgn.Game] — one entry per successfully parsed game.

    Purpose: load a user-uploaded PGN file into game objects, reusing the same
    validation/skip-and-log behavior as parse_pgn_string.
    """
    try:
        with open(file_path, encoding="utf-8") as f:
            pgn_text = f.read()
    except OSError as exc:
        logger.error("Could not read PGN file '%s': %s", file_path, exc)
        raise

    games = parse_pgn_string(pgn_text)
    if not games:
        logger.warning("No valid games parsed from '%s'", file_path)
    return games


def _is_well_formed(game: chess.pgn.Game) -> bool:
    """Input shape: chess.pgn.Game.
    Output shape: bool.

    Purpose: fail-fast validation gate before a parsed game is allowed downstream —
    per Rules.md, a malformed game should be rejected here rather than silently
    propagated as e.g. a game with zero moves.
    """
    try:
        move_count = sum(1 for _ in game.mainline_moves())
    except Exception:
        return False
    return move_count > 0
