"""Positional feature extraction: material balance, king safety, pawn structure,
and game phase, computed per position (per move row in the annotated DataFrame).
"""

import chess
import pandas as pd

MATERIAL_VALUES = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
    chess.KING: 0,
}

# Judgment-call thresholds (not specified in project docs), documented in Memory.md:
# a position is "endgame" once combined non-pawn material drops to a quarter or less
# of the full-board total (62), and "opening" is anything at/under move 10 that isn't
# already an endgame by that material test.
ENDGAME_MATERIAL_THRESHOLD = 14
OPENING_MOVE_NUMBER_CUTOFF = 10


def material_balance(board: chess.Board) -> int:
    """Input shape: chess.Board.
    Output shape: int, White's total material minus Black's (pawn=1 .. queen=9, king
    excluded), positive favors White.

    Purpose: cheap, standard material-count feature for a position.
    """
    balance = 0
    for piece in board.piece_map().values():
        value = MATERIAL_VALUES[piece.piece_type]
        balance += value if piece.color == chess.WHITE else -value
    return balance


def king_safety(board: chess.Board, color: chess.Color) -> int:
    """Input shape: chess.Board, color (chess.WHITE or chess.BLACK) — whose king to score.
    Output shape: int, higher = safer.

    Purpose: heuristic king-safety score = (number of the king's own 3 home files
    with an own pawn within 2 ranks in front of the king) minus (number of those
    3 files with no pawns of either color, i.e. fully open lines to the king).
    """
    king_square = board.king(color)
    if king_square is None:
        return 0
    king_file = chess.square_file(king_square)
    king_rank = chess.square_rank(king_square)
    forward = 1 if color == chess.WHITE else -1

    shield = 0
    open_files = 0
    for f in range(max(0, king_file - 1), min(7, king_file + 1) + 1):
        own_pawn_near = False
        any_pawn_on_file = False
        for r in range(8):
            piece = board.piece_at(chess.square(f, r))
            if piece and piece.piece_type == chess.PAWN:
                any_pawn_on_file = True
                if piece.color == color and 0 <= (r - king_rank) * forward <= 2:
                    own_pawn_near = True
        if own_pawn_near:
            shield += 1
        if not any_pawn_on_file:
            open_files += 1

    return shield - open_files


def pawn_structure(board: chess.Board, color: chess.Color) -> str:
    """Input shape: chess.Board, color (chess.WHITE or chess.BLACK) — whose pawns to assess.
    Output shape: str, one of 'isolated' | 'doubled' | 'normal'.

    Purpose: flag the dominant pawn-structure weakness for `color`. Scoped to
    isolated and doubled pawns only (backward-pawn detection needs a more involved
    heuristic and is out of scope for this project, per Rules.md's brittleness
    warning on heuristic detectors — documented judgment call). Isolated is
    reported ahead of doubled when both are present, since an isolated pawn is
    generally the more serious long-term weakness.
    """
    pawn_files = [chess.square_file(sq) for sq in board.pieces(chess.PAWN, color)]
    file_set = set(pawn_files)

    doubled = any(pawn_files.count(f) > 1 for f in file_set)
    isolated = any(not ({f - 1, f + 1} & file_set) for f in file_set)

    if isolated:
        return "isolated"
    if doubled:
        return "doubled"
    return "normal"


def game_phase(board: chess.Board, move_number: int) -> str:
    """Input shape: chess.Board, move_number int (1-indexed full-move-pair count from
    the annotation layer).
    Output shape: str, one of 'opening' | 'middlegame' | 'endgame'.

    Purpose: coarse phase classification combining remaining material and move
    number (see module-level threshold constants for the exact judgment call).
    """
    non_pawn_material = sum(
        MATERIAL_VALUES[p.piece_type]
        for p in board.piece_map().values()
        if p.piece_type not in (chess.PAWN, chess.KING)
    )
    if non_pawn_material <= ENDGAME_MATERIAL_THRESHOLD:
        return "endgame"
    if move_number <= OPENING_MOVE_NUMBER_CUTOFF:
        return "opening"
    return "middlegame"


def extract_positional_features(fen: str, move_number: int) -> dict:
    """Input shape: fen str, move_number int.
    Output shape: dict {material_balance: int, king_safety: int, pawn_structure: str,
    phase: str} — king_safety/pawn_structure are computed for the side to move in `fen`.

    Purpose: single-position feature bundle, the unit extract_all_features() maps
    over every row of the annotated DataFrame.
    """
    board = chess.Board(fen)
    mover_color = board.turn
    return {
        "material_balance": material_balance(board),
        "king_safety": king_safety(board, mover_color),
        "pawn_structure": pawn_structure(board, mover_color),
        "phase": game_phase(board, move_number),
    }


def add_positional_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Input shape: pd.DataFrame with at least {fen, move_number} columns.
    Output shape: copy of df with new columns material_balance, king_safety,
    pawn_structure, phase.

    Purpose: row-wise wrapper applying extract_positional_features() across the
    annotated-moves DataFrame.
    """
    df = df.copy()
    if df.empty:
        for col in ("material_balance", "king_safety", "pawn_structure", "phase"):
            df[col] = pd.Series(dtype="object")
        return df

    feature_dicts = df.apply(
        lambda row: extract_positional_features(row["fen"], row["move_number"]), axis=1
    )
    feature_df = pd.DataFrame(list(feature_dicts), index=df.index)
    for col in feature_df.columns:
        df[col] = feature_df[col]
    return df
