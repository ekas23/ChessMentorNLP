"""Shared test helpers: build annotated move rows without running Stockfish."""

import shutil

import chess
import pandas as pd
import pytest

from src.annotation.classify_moves import classify_moves_df

requires_stockfish = pytest.mark.skipif(
    shutil.which("stockfish") is None and not any(
        __import__("pathlib").Path(p).is_file() for p in ("/usr/games/stockfish", "/usr/local/bin/stockfish")
    ),
    reason="Stockfish binary not installed",
)


def rows_from_moves(sans, evals, game_id="g1", player_side="white", best=None, start_fen=chess.STARTING_FEN):
    """Build annotation rows for a sequence of SAN moves.

    evals: White-POV evaluation of every position (len(sans) + 1 values).
    best: optional list of engine best-move UCIs per ply (default: the played move, i.e. no error).
    """
    board = chess.Board(start_fen)
    rows = []
    for i, san in enumerate(sans):
        move = board.parse_san(san)
        side = "white" if board.turn == chess.WHITE else "black"
        rows.append({
            "game_id": game_id, "ply": i + 1, "move_number": board.fullmove_number, "side": side,
            "is_player": side == player_side, "fen": board.fen(), "move_uci": move.uci(), "move_san": san,
            "eval_before": evals[i], "eval_after": evals[i + 1],
            "best_move_uci": (best[i] if best else move.uci()), "best_reply_uci": None,
        })
        board.push(move)
    return classify_moves_df(pd.DataFrame(rows))
