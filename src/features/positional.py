"""Positional features per move: material balance, king safety, game phase, and
pawn-structure weaknesses CREATED by the move.

Pawn structure used to be recorded as a board state ("isolated"/"doubled"/
"normal") on every row, for whichever side was to move. Almost every middlegame
has some isolated or doubled pawn somewhere, so that counted the same weakness
on every move, for both players. It is now an event: a move counts only if it
gives the mover a new isolated or doubled pawn that was not there before.
"""

from __future__ import annotations

import chess
import pandas as pd

MATERIAL_VALUES = {
    chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 0,
}

# Endgame once non-pawn material (both sides, excluding kings) is <= 14 of the 62
# starting points; otherwise "opening" through full move 10, then "middlegame".
ENDGAME_MATERIAL_THRESHOLD = 14
OPENING_FULLMOVE_CUTOFF = 10

FILE_NAMES = "abcdefgh"


def material_balance(board: chess.Board) -> int:
    """Input: board. Output: White material minus Black material (pawn = 1 ... queen = 9)."""
    balance = 0
    for piece in board.piece_map().values():
        value = MATERIAL_VALUES[piece.piece_type]
        balance += value if piece.color == chess.WHITE else -value
    return balance


def king_safety(board: chess.Board, color: chess.Color) -> int:
    """Input: board, colour. Output: pawn-shield files minus fully open files around the king."""
    king_square = board.king(color)
    if king_square is None:
        return 0
    king_file = chess.square_file(king_square)
    king_rank = chess.square_rank(king_square)
    forward = 1 if color == chess.WHITE else -1
    shield = open_files = 0
    for f in range(max(0, king_file - 1), min(7, king_file + 1) + 1):
        own_near = any_pawn = False
        for r in range(8):
            piece = board.piece_at(chess.square(f, r))
            if piece and piece.piece_type == chess.PAWN:
                any_pawn = True
                if piece.color == color and 0 <= (r - king_rank) * forward <= 2:
                    own_near = True
        shield += own_near
        open_files += not any_pawn
    return shield - open_files


def pawn_weak_files(board: chess.Board, color: chess.Color) -> dict[str, set[int]]:
    """Input: board, colour. Output: {'isolated': files with an isolated pawn,
    'doubled': files with 2+ pawns} for that colour's pawns."""
    files = [chess.square_file(sq) for sq in board.pieces(chess.PAWN, color)]
    file_set = set(files)
    return {
        "isolated": {f for f in file_set if not ({f - 1, f + 1} & file_set)},
        "doubled": {f for f in file_set if files.count(f) > 1},
    }


def pawn_weakness_created(board_before: chess.Board, move: chess.Move) -> str:
    """Input: board before the move, the move. Output: a short description of any new
    isolated/doubled pawn the move gives the MOVER (e.g. 'doubled pawns on the c-file'),
    or '' if none."""
    color = board_before.turn
    before = pawn_weak_files(board_before, color)
    after_board = board_before.copy(stack=False)
    after_board.push(move)
    after = pawn_weak_files(after_board, color)
    parts = []
    for f in sorted(after["doubled"] - before["doubled"]):
        parts.append(f"doubled pawns on the {FILE_NAMES[f]}-file")
    for f in sorted(after["isolated"] - before["isolated"]):
        parts.append(f"an isolated pawn on the {FILE_NAMES[f]}-file")
    return " and ".join(parts)


def game_phase(board: chess.Board, fullmove_number: int) -> str:
    """Input: board, full-move number. Output: 'opening' | 'middlegame' | 'endgame'."""
    non_pawn = sum(
        MATERIAL_VALUES[p.piece_type]
        for p in board.piece_map().values()
        if p.piece_type not in (chess.PAWN, chess.KING)
    )
    if non_pawn <= ENDGAME_MATERIAL_THRESHOLD:
        return "endgame"
    if fullmove_number <= OPENING_FULLMOVE_CUTOFF:
        return "opening"
    return "middlegame"


def add_positional_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Input: annotation DataFrame (fen, move_uci, move_number).
    Output: copy with material_balance, king_safety (mover), phase, pawn_weakness_created."""
    df = df.copy()
    cols = ("material_balance", "king_safety", "phase", "pawn_weakness_created")
    if df.empty:
        for col in cols:
            df[col] = pd.Series(dtype="object")
        return df
    out = {c: [] for c in cols}
    for fen, uci, fullmove in zip(df["fen"], df["move_uci"], df["move_number"]):
        board = chess.Board(fen)
        out["material_balance"].append(material_balance(board))
        out["king_safety"].append(king_safety(board, board.turn))
        out["phase"].append(game_phase(board, int(fullmove)))
        out["pawn_weakness_created"].append(pawn_weakness_created(board, chess.Move.from_uci(uci)))
    for col in cols:
        df[col] = out[col]
    return df
