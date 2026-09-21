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


def _fork_detail(board: chess.Board) -> dict | None:
    """Input shape: chess.Board.
    Output shape: dict {attacker_square, attacker_piece_type, target_squares: list[Square],
    target_piece_types: list[PieceType]} for the first qualifying fork found, or None.

    Purpose: shared detection+detail logic for detect_fork() and describe_motifs() —
    computed once, in one place, so the boolean check and the human-readable
    description can never drift apart or disagree about what was found.
    """
    attacker_color = board.turn
    defender_color = not attacker_color
    for square, piece in board.piece_map().items():
        if piece.color != attacker_color:
            continue
        attacked_squares = board.attacks(square)
        targets = [
            sq
            for sq in attacked_squares
            if (target := board.piece_at(sq)) is not None
            and target.color == defender_color
            and target.piece_type != chess.PAWN
        ]
        if len(targets) >= 2:
            return {
                "attacker_square": square,
                "attacker_piece_type": piece.piece_type,
                "target_squares": targets,
                "target_piece_types": [board.piece_at(sq).piece_type for sq in targets],
            }
    return None


def detect_fork(board: chess.Board) -> bool:
    """Input shape: chess.Board.
    Output shape: bool.

    Purpose: True if the side to move has any single piece simultaneously
    attacking 2+ enemy non-pawn pieces (a fork).
    """
    return _fork_detail(board) is not None


def _pin_detail(board: chess.Board) -> dict | None:
    """Input shape: chess.Board.
    Output shape: dict {pinned_square, pinned_piece_type} for the first pinned piece
    found, or None. See _fork_detail() for why detection and detail share one function.
    """
    defender_color = not board.turn
    for square, piece in board.piece_map().items():
        if piece.color == defender_color and piece.piece_type != chess.KING:
            if board.is_pinned(defender_color, square):
                return {"pinned_square": square, "pinned_piece_type": piece.piece_type}
    return None


def detect_pin(board: chess.Board) -> bool:
    """Input shape: chess.Board.
    Output shape: bool.

    Purpose: True if any non-king piece belonging to the side NOT to move is
    absolutely pinned to its own king (python-chess's is_pinned, which accounts
    for the full board regardless of whose turn it is).
    """
    return _pin_detail(board) is not None


def _skewer_detail(board: chess.Board) -> dict | None:
    """Input shape: chess.Board.
    Output shape: dict {front_square, front_piece_type, back_square, back_piece_type}
    for the first qualifying skewer found, or None. See _fork_detail() for why
    detection and detail share one function.
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
            (front_sq, front), (back_sq, back) = occupied
            if front.color != defender_color or back.color != defender_color:
                continue
            if _SKEWER_VALUES[front.piece_type] >= _SKEWER_VALUES[back.piece_type]:
                return {
                    "front_square": front_sq,
                    "front_piece_type": front.piece_type,
                    "back_square": back_sq,
                    "back_piece_type": back.piece_type,
                }
    return None


def detect_skewer(board: chess.Board) -> bool:
    """Input shape: chess.Board.
    Output shape: bool.

    Purpose: True if a sliding piece (rook/bishop/queen) belonging to the side
    to move has a clear ray onto two enemy pieces in a line, where the nearer
    ("front") piece is worth at least as much as the farther ("back") one —
    the classic skewer pattern (attacking the front piece threatens to win the
    back piece once the front piece moves or is captured).
    """
    return _skewer_detail(board) is not None


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


def describe_motifs(board: chess.Board) -> str:
    """Input shape: chess.Board.
    Output shape: str, a short plain-language clause naming the specific piece(s)/
    square(s) involved in the most prominent motif present (priority fork > pin >
    skewer, matching detect_motifs()'s order), or "" if none detected.

    Purpose: give the NLP layer's per-instance narration (nlp/instances.py) a
    concrete, non-fabricated detail to reference -- e.g. "a knight fork on f5
    attacking your queen and rook" -- derived purely from the same board analysis
    detect_motifs() already performs, never invented. This is the answer to the
    2026-09-22 change request's question of whether the data model retains enough
    detail to narrate "what was missed": detect_fork/pin/skewer originally returned
    only booleans, which was NOT enough for concrete narration -- this function
    (and the _*_detail() helpers above) is the small, additive Phase 3 extension
    flagged in Memory.md rather than silently fabricating position specifics.
    """
    # NOTE: detect_fork/pin/skewer all run from the side-to-move's (the mover's) own
    # perspective -- the pieces involved as *targets* (fork targets, the pinned piece,
    # the skewered pair) belong to the opponent (the side NOT to move), since these
    # functions detect a tactical opportunity the mover had available against the
    # opponent. Wording below says "the opponent's" for target pieces accordingly --
    # saying "your" here would misattribute the pieces to the wrong side.
    fork = _fork_detail(board)
    if fork is not None:
        attacker_name = chess.piece_name(fork["attacker_piece_type"])
        target_names = [chess.piece_name(pt) for pt in fork["target_piece_types"]]
        targets_text = " and ".join(f"the opponent's {name}" for name in target_names)
        return (
            f"a {attacker_name} fork on {chess.square_name(fork['attacker_square'])} "
            f"attacking {targets_text}"
        )

    pin = _pin_detail(board)
    if pin is not None:
        pinned_name = chess.piece_name(pin["pinned_piece_type"])
        return f"a pin on the opponent's {pinned_name} on {chess.square_name(pin['pinned_square'])}"

    skewer = _skewer_detail(board)
    if skewer is not None:
        front_name = chess.piece_name(skewer["front_piece_type"])
        back_name = chess.piece_name(skewer["back_piece_type"])
        return (
            f"a skewer hitting the opponent's {front_name} on "
            f"{chess.square_name(skewer['front_square'])}, with their {back_name} on "
            f"{chess.square_name(skewer['back_square'])} behind it"
        )

    return ""


def add_motif_column(df: pd.DataFrame) -> pd.DataFrame:
    """Input shape: pd.DataFrame with at least a {fen} column.
    Output shape: copy of df with two new columns: 'motif' (comma-joined tags, e.g.
    'fork,pin', or '' if none) and 'motif_detail' (a short plain-language clause
    naming the specific piece(s)/square(s) for the primary motif, or '' if none —
    see describe_motifs()).

    Purpose: row-wise wrapper computing both the tag and its human-readable detail
    from one board per row (single fen->Board parse), so callers needing the
    instance-narration detail don't have to re-parse every FEN a second time.
    """
    df = df.copy()
    if df.empty:
        df["motif"] = pd.Series(dtype="object")
        df["motif_detail"] = pd.Series(dtype="object")
        return df

    boards = df["fen"].apply(chess.Board)
    df["motif"] = boards.apply(lambda b: ",".join(detect_motifs(b)))
    df["motif_detail"] = boards.apply(describe_motifs)
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
