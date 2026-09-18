"""Stockfish wrapper: per-move centipawn evaluation for a parsed game.

Produces the Annotation layer's contribution to the Annotation -> Features
data contract (Architecture.md §4): one row per move with
{game_id, move_number, fen, move_uci, eval_before, eval_after}. The
quality_label column is added afterward by classify_moves.py.
"""

import logging

import chess
import chess.pgn
import pandas as pd
from stockfish import Stockfish

from src.annotation.classify_moves import classify_moves_df
from src.config import resolve_stockfish_path

logger = logging.getLogger(__name__)

DEFAULT_DEPTH = 12
MATE_SCORE_CP = 10000

ANNOTATION_COLUMNS = ["game_id", "move_number", "fen", "move_uci", "eval_before", "eval_after"]


class AnnotationError(Exception):
    """Raised when a game cannot be fully, reliably annotated."""


def create_engine(depth: int = DEFAULT_DEPTH, path: str | None = None) -> Stockfish:
    """Input shape: depth int (search depth), path optional str (Stockfish binary path).
    Output shape: a live Stockfish instance.

    Purpose: start one reusable Stockfish process for annotating many positions —
    creating a fresh process per position would be far too slow for a whole game.
    """
    resolved_path = path or resolve_stockfish_path()
    try:
        return Stockfish(path=resolved_path, depth=depth)
    except Exception as exc:
        logger.error("Failed to start Stockfish at '%s': %s", resolved_path, exc)
        raise


def evaluate_fen(engine: Stockfish, fen: str) -> float:
    """Input shape: engine (live Stockfish instance), fen str.
    Output shape: float, centipawns from White's perspective (positive = White better).

    Purpose: evaluate a single position. Mate scores are converted to a large finite
    centipawn value (sign matching the mating side) so downstream eval-swing math
    never has to special-case a mate score vs. a centipawn score.
    """
    try:
        engine.set_fen_position(fen)
        raw = engine.get_evaluation()
    except Exception as exc:
        raise AnnotationError(f"Stockfish evaluation failed for FEN '{fen}': {exc}") from exc

    if not raw or "type" not in raw or "value" not in raw:
        raise AnnotationError(f"Stockfish returned no usable evaluation for FEN '{fen}': {raw}")

    if raw["type"] == "mate":
        mate_in = raw["value"]
        sign = 1 if mate_in > 0 else -1
        return float(sign * (MATE_SCORE_CP - abs(mate_in) * 10))
    return float(raw["value"])


def annotate_game(game: chess.pgn.Game, game_id: str, engine: Stockfish) -> list[dict]:
    """Input shape: game (chess.pgn.Game), game_id str, engine (live Stockfish instance).
    Output shape: list[dict], one per move, each with keys
    {game_id, move_number, fen, move_uci, eval_before, eval_after}.

    Purpose: walk a game's mainline, evaluating the position before and after each
    move. Each move's eval_before is the previous move's eval_after, so only N+1
    engine calls are needed for an N-move game rather than 2N.
    Raises AnnotationError if any single position fails to evaluate — the caller is
    expected to skip and log the whole game rather than pass a partially-annotated
    game downstream (Rules.md: never silently propagate incomplete data).
    """
    board = game.board()
    eval_before = evaluate_fen(engine, board.fen())

    rows = []
    move_number = 0
    for move in game.mainline_moves():
        move_number += 1
        fen_before = board.fen()
        board.push(move)
        eval_after = evaluate_fen(engine, board.fen())

        rows.append(
            {
                "game_id": game_id,
                "move_number": move_number,
                "fen": fen_before,
                "move_uci": move.uci(),
                "eval_before": eval_before,
                "eval_after": eval_after,
            }
        )
        eval_before = eval_after

    return rows


def annotate_games(games: list[chess.pgn.Game], depth: int = DEFAULT_DEPTH) -> pd.DataFrame:
    """Input shape: games list[chess.pgn.Game].
    Output shape: pd.DataFrame matching Architecture.md §4's Annotation->Features contract:
    columns {game_id, move_number, fen, move_uci, eval_before, eval_after, quality_label}.

    Purpose: end-to-end batch annotation entry point. Reuses one Stockfish process
    across all games for speed. A game that fails partway through annotation is
    skipped and logged (Rules.md §2); the rest of the batch continues.
    """
    engine = create_engine(depth=depth)
    all_rows: list[dict] = []
    for index, game in enumerate(games):
        game_id = _derive_game_id(game, index)
        try:
            rows = annotate_game(game, game_id, engine)
        except AnnotationError as exc:
            logger.warning("Skipping game '%s': %s", game_id, exc)
            continue
        all_rows.extend(rows)

    df = pd.DataFrame(all_rows, columns=ANNOTATION_COLUMNS)
    return classify_moves_df(df)


def _derive_game_id(game: chess.pgn.Game, index: int) -> str:
    """Input shape: game (chess.pgn.Game), index int (position in the batch).
    Output shape: str, a stable-enough identifier for the game.

    Purpose: build a human-readable game_id from PGN headers, falling back to the
    batch index if headers are missing (e.g. a bare PGN with no metadata).
    """
    headers = game.headers
    white = headers.get("White", "?")
    black = headers.get("Black", "?")
    date = headers.get("Date", "????.??.??")
    round_ = headers.get("Round", "?")
    if white == "?" and black == "?":
        return f"game_{index}"
    return f"{date}_{white}_vs_{black}_r{round_}_{index}"
