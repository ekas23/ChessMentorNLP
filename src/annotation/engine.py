"""Stockfish annotation: one row per half-move with engine evaluations.

Uses python-chess's own UCI engine interface (chess.engine) rather than the
`stockfish` pip wrapper. The wrapper changed its default in v4+/v5 to report
scores from the side-to-move's perspective, while this project assumed White's
perspective -- that mismatch labelled almost every move by the winning side as a
blunder (see Memory.md, 2026-10-19). chess.engine returns a PovScore, and we
always read it explicitly from White's point of view, so the convention can no
longer silently change under us.

Output contract (Annotation -> Features, Architecture.md §4), one row per ply:
  game_id, ply, move_number (full-move number as printed in PGN), side
  ('white'|'black'), is_player (bool), fen (position BEFORE the move),
  move_uci, move_san, eval_before, eval_after (centipawns, White's POV, clipped
  to +/-MATE_SCORE_CP), best_move_uci (engine's choice in `fen`),
  best_reply_uci (engine's choice in the position after the move).
quality_label / win-chance columns are added by classify_moves.py.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

import chess
import chess.engine
import chess.pgn
import pandas as pd

from src.annotation.classify_moves import classify_moves_df
from src.config import ANNOTATED_DIR, resolve_stockfish_path

logger = logging.getLogger(__name__)

DEFAULT_DEPTH = 14
# Mate scores are mapped to +/-1000 cp (minus distance to mate) and every score is
# clipped to that range. 1000 cp is already "completely winning"; larger values only
# create artificial 10,000-cp "swings" between two lost positions.
MATE_SCORE_CP = 1000

ANNOTATION_COLUMNS = [
    "game_id", "ply", "move_number", "side", "is_player", "fen", "move_uci", "move_san",
    "eval_before", "eval_after", "best_move_uci", "best_reply_uci",
]

CACHE_DIR = ANNOTATED_DIR / "cache"


class AnnotationError(Exception):
    """Raised when a game cannot be fully, reliably annotated."""


def create_engine(path: str | None = None) -> chess.engine.SimpleEngine:
    """Input: optional path to a Stockfish binary. Output: a running UCI engine.

    Purpose: start one engine process to reuse across a whole batch. The caller
    must call .quit() (annotate_games does this in a finally block).
    """
    resolved_path = path or resolve_stockfish_path()
    try:
        return chess.engine.SimpleEngine.popen_uci(resolved_path)
    except Exception as exc:  # noqa: BLE001 - surface a clear message, then re-raise
        logger.error("Failed to start Stockfish at '%s': %s", resolved_path, exc)
        raise


def _terminal_eval(board: chess.Board) -> float | None:
    """Input: a board. Output: White-POV cp for a finished game, or None if not finished.

    Purpose: never ask the engine to score checkmate/stalemate. Checkmate is scored
    as a full win for the side that delivered it; any drawn ending is 0.
    """
    if board.is_checkmate():
        # board.turn is the side that has been mated.
        return float(-MATE_SCORE_CP if board.turn == chess.WHITE else MATE_SCORE_CP)
    if board.is_game_over(claim_draw=False):
        return 0.0
    return None


def analyse_position(engine, board: chess.Board, depth: int) -> tuple[float, str | None]:
    """Input: engine, board, search depth.
    Output: (eval in centipawns from White's POV, clipped; engine best move as UCI or None).

    Purpose: the single place an evaluation is produced, so the perspective and
    mate-score conventions are defined exactly once.
    """
    terminal = _terminal_eval(board)
    if terminal is not None:
        return terminal, None
    try:
        info = engine.analyse(board, chess.engine.Limit(depth=depth))
    except Exception as exc:  # noqa: BLE001
        raise AnnotationError(f"Stockfish analysis failed for FEN '{board.fen()}': {exc}") from exc

    score = info.get("score")
    if score is None:
        raise AnnotationError(f"Stockfish returned no score for FEN '{board.fen()}'")
    cp = score.white().score(mate_score=MATE_SCORE_CP)
    cp = max(-MATE_SCORE_CP, min(MATE_SCORE_CP, cp))
    pv = info.get("pv") or []
    return float(cp), (pv[0].uci() if pv else None)


def player_color(game: chess.pgn.Game, username: str | None) -> chess.Color | None:
    """Input: game, username. Output: chess.WHITE / chess.BLACK, or None if the
    username is neither player (case-insensitive match on the PGN headers)."""
    if not username:
        return None
    name = username.strip().lower()
    if game.headers.get("White", "").strip().lower() == name:
        return chess.WHITE
    if game.headers.get("Black", "").strip().lower() == name:
        return chess.BLACK
    return None


def annotate_game(
    game: chess.pgn.Game, game_id: str, engine, depth: int, color: chess.Color | None
) -> list[dict]:
    """Input: game, game_id, engine, depth, the analysed player's colour (None marks
    every move as a player move -- used only for colour-less fixtures).
    Output: list of row dicts in the ANNOTATION_COLUMNS shape.

    Purpose: walk the mainline evaluating every position once (N+1 engine calls for N
    plies); each position's best move doubles as the previous move's best reply.
    """
    board = game.board()
    evals: list[float] = []
    bests: list[str | None] = []
    plies: list[tuple[str, str, str, chess.Color, int]] = []

    cp, best = analyse_position(engine, board, depth)
    evals.append(cp)
    bests.append(best)
    for move in game.mainline_moves():
        fen_before = board.fen()
        san = board.san(move)
        side = board.turn
        fullmove = board.fullmove_number
        board.push(move)
        cp, best = analyse_position(engine, board, depth)
        evals.append(cp)
        bests.append(best)
        plies.append((fen_before, move.uci(), san, side, fullmove))

    rows = []
    for i, (fen_before, uci, san, side, fullmove) in enumerate(plies):
        rows.append({
            "game_id": game_id,
            "ply": i + 1,
            "move_number": fullmove,
            "side": "white" if side == chess.WHITE else "black",
            "is_player": True if color is None else side == color,
            "fen": fen_before,
            "move_uci": uci,
            "move_san": san,
            "eval_before": evals[i],
            "eval_after": evals[i + 1],
            "best_move_uci": bests[i],
            "best_reply_uci": bests[i + 1],
        })
    return rows


def _cache_path(game: chess.pgn.Game, depth: int) -> Path:
    exporter = chess.pgn.StringExporter(headers=False, variations=False, comments=False)
    key = f"{game.headers.get('Link', '')}|{game.accept(exporter)}|{depth}|v2"
    return CACHE_DIR / f"{hashlib.sha1(key.encode()).hexdigest()}.csv"


def annotate_games(
    games: list[chess.pgn.Game],
    depth: int = DEFAULT_DEPTH,
    username: str | None = None,
    game_ids: list[str] | None = None,
    use_cache: bool = True,
    engine_path: str | None = None,
) -> pd.DataFrame:
    """Input: games, search depth, the analysed player's username, optional game_ids
    (defaults to derive_game_id), use_cache (re-use annotations saved on disk).
    Output: DataFrame in the ANNOTATION_COLUMNS shape plus classify_moves columns.

    Purpose: batch entry point. Engine work is cached per game+depth under
    data/annotated/cache so re-running a report or a cohort evaluation does not
    re-analyse games already seen. A game whose analysis fails is logged and skipped.
    """
    game_ids = game_ids or [derive_game_id(g, i) for i, g in enumerate(games)]
    frames: list[pd.DataFrame] = []
    engine = None
    try:
        for game, game_id in zip(games, game_ids, strict=True):
            color = player_color(game, username)
            if username and color is None:
                logger.warning("Skipping game '%s': '%s' is not one of its players", game_id, username)
                continue
            path = _cache_path(game, depth)
            if use_cache and path.is_file():
                cached = pd.read_csv(path, keep_default_na=False, na_values=[""])
                cached["game_id"] = game_id
                cached["is_player"] = cached["side"].map(
                    lambda s: True if color is None else (s == ("white" if color == chess.WHITE else "black"))
                )
                frames.append(cached[ANNOTATION_COLUMNS])
                continue
            if engine is None:
                engine = create_engine(engine_path)
            try:
                rows = annotate_game(game, game_id, engine, depth, color)
            except AnnotationError as exc:
                logger.warning("Skipping game '%s': %s", game_id, exc)
                continue
            frame = pd.DataFrame(rows, columns=ANNOTATION_COLUMNS)
            if use_cache and not frame.empty:
                try:
                    CACHE_DIR.mkdir(parents=True, exist_ok=True)
                    frame.to_csv(path, index=False)
                except OSError as exc:
                    logger.warning("Could not write annotation cache '%s': %s", path, exc)
            frames.append(frame)
    finally:
        if engine is not None:
            engine.quit()

    df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=ANNOTATION_COLUMNS)
    for col in ("best_move_uci", "best_reply_uci"):
        df[col] = df[col].astype(object).where(df[col].notna(), None)
    return classify_moves_df(df)


def derive_game_id(game: chess.pgn.Game, index: int) -> str:
    """Input: game, its index in the batch. Output: a readable, unique-in-batch id."""
    headers = game.headers
    white = headers.get("White", "?")
    black = headers.get("Black", "?")
    date = headers.get("Date", "????.??.??")
    if white == "?" and black == "?":
        return f"game_{index}"
    return f"{date}_{white}_vs_{black}_{index}"
