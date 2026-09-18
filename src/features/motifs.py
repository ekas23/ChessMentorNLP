"""Tactical motif detection: fork, pin, skewer — scoped to exactly these 3 per
PRD.md's risk note that rule-based motif detection is brittle. These are
heuristic pattern detectors on a single position, not a full tactics solver:
they flag that a motif's geometric pattern is present for the side to move,
not that it's necessarily the best or a winning move.
"""

import chess
import pandas as pd

# King given an effectively-infinite value here (not in positional.py's material
# table) so a check-producing skewer (king in front, piece behind) always counts.
_SKEWER_VALUES = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
    chess.KING: 1000,
}

_ROOK_DIRECTIONS = [(1, 0), (-1, 0), (0, 1), (0, -1)]
_BISHOP_DIRECTIONS = [(1, 1), (1, -1), (-1, 1), (-1, -1)]


def detect_fork(board: chess.Board) -> bool:
    """Input shape: chess.Board.
    Output shape: bool.

    Purpose: True if the side to move has any single piece simultaneously
    attacking 2+ enemy non-pawn pieces (a fork).
    """
    attacker_color = board.turn
    defender_color = not attacker_color
    for square, piece in board.piece_map().items():
        if piece.color != attacker_color:
            continue
        attacked_squares = board.attacks(square)
        valuable_targets = [
            sq
            for sq in attacked_squares
            if (target := board.piece_at(sq)) is not None
            and target.color == defender_color
            and target.piece_type != chess.PAWN
        ]
        if len(valuable_targets) >= 2:
            return True
    return False


def detect_pin(board: chess.Board) -> bool:
    """Input shape: chess.Board.
    Output shape: bool.

    Purpose: True if any non-king piece belonging to the side NOT to move is
    absolutely pinned to its own king (python-chess's is_pinned, which accounts
    for the full board regardless of whose turn it is).
    """
    defender_color = not board.turn
    for square, piece in board.piece_map().items():
        if piece.color == defender_color and piece.piece_type != chess.KING:
            if board.is_pinned(defender_color, square):
                return True
    return False


def detect_skewer(board: chess.Board) -> bool:
    """Input shape: chess.Board.
    Output shape: bool.

    Purpose: True if a sliding piece (rook/bishop/queen) belonging to the side
    to move has a clear ray onto two enemy pieces in a line, where the nearer
    ("front") piece is worth at least as much as the farther ("back") one —
    the classic skewer pattern (attacking the front piece threatens to win the
    back piece once the front piece moves or is captured).
    """
    attacker_color = board.turn
    defender_color = not attacker_color
    for square, piece in board.piece_map().items():
        if piece.color != attacker_color or piece.piece_type not in (
            chess.ROOK,
            chess.BISHOP,
            chess.QUEEN,
        ):
            continue
        for df, dr in _directions_for(piece.piece_type):
            occupied = [
                (sq, board.piece_at(sq)) for sq in _walk_ray(square, df, dr) if board.piece_at(sq)
            ][:2]
            if len(occupied) < 2:
                continue
            (_, front), (_, back) = occupied
            if front.color != defender_color or back.color != defender_color:
                continue
            if _SKEWER_VALUES[front.piece_type] >= _SKEWER_VALUES[back.piece_type]:
                return True
    return False


def detect_motifs(board: chess.Board) -> list[str]:
    """Input shape: chess.Board.
    Output shape: list[str], any of 'fork', 'pin', 'skewer' present in the position
    (empty list if none detected).

    Purpose: combined entry point run once per position by add_motif_column().
    """
    motifs = []
    if detect_fork(board):
        motifs.append("fork")
    if detect_pin(board):
        motifs.append("pin")
    if detect_skewer(board):
        motifs.append("skewer")
    return motifs


def add_motif_column(df: pd.DataFrame) -> pd.DataFrame:
    """Input shape: pd.DataFrame with at least a {fen} column.
    Output shape: copy of df with a new 'motif' column — a comma-joined string of
    detected tags (e.g. 'fork,pin'), or '' if none detected for that position.

    Purpose: row-wise wrapper applying detect_motifs() across the annotated-moves
    DataFrame.
    """
    df = df.copy()
    if df.empty:
        df["motif"] = pd.Series(dtype="object")
        return df
    df["motif"] = df["fen"].apply(lambda fen: ",".join(detect_motifs(chess.Board(fen))))
    return df


def _directions_for(piece_type: chess.PieceType) -> list[tuple[int, int]]:
    """Input shape: chess.PieceType. Output shape: list of (file_delta, rank_delta) tuples.
    Purpose: the sliding directions a piece type can attack along.
    """
    if piece_type == chess.ROOK:
        return _ROOK_DIRECTIONS
    if piece_type == chess.BISHOP:
        return _BISHOP_DIRECTIONS
    if piece_type == chess.QUEEN:
        return _ROOK_DIRECTIONS + _BISHOP_DIRECTIONS
    return []


def _walk_ray(start_square: chess.Square, df: int, dr: int):
    """Input shape: start_square (chess.Square), df/dr int deltas per step.
    Output shape: generator of chess.Square, walking outward from start_square
    (exclusive) until the board edge.

    Purpose: shared ray-walk used by detect_skewer() to inspect squares beyond
    python-chess's built-in attacks() (which stops at the first blocker).
    """
    file_, rank_ = chess.square_file(start_square), chess.square_rank(start_square)
    while True:
        file_, rank_ = file_ + df, rank_ + dr
        if not (0 <= file_ <= 7 and 0 <= rank_ <= 7):
            return
        yield chess.square(file_, rank_)
