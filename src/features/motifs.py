"""Tactical motifs (fork, pin, skewer) and missed-tactic detection.

Old behaviour (removed 2026-10-19): a motif was "present" if its geometry
existed anywhere on the board for the side to move, and a "missed tactic" was any
mistake played in such a position. That fired on things that are not tactics at
all -- e.g. a bishop "skewering" two pawns -- and never checked what the engine
actually wanted to play.

New behaviour: a motif is attributed to a specific MOVE. We push the move and
check whether the moved piece now
  - forks: attacks two or more enemy targets, each being the king, a piece worth
    more than the attacker, or an undefended piece (pawns never count as targets);
  - pins: pins an enemy non-pawn piece to its king (a newly created absolute pin);
  - skewers: attacks, along a line, an enemy king/queen/rook with a less valuable
    non-pawn piece directly behind it.
A move is a MISSED TACTIC when (1) the engine's best move creates a motif,
(2) the player played a different move that does not create the same motif, and
(3) the played move was at least a mistake (winning chances fell by >= 0.2).
These are still heuristics; RQ1 in docs/EVALUATION.md measures their precision.
"""

from __future__ import annotations

import chess
import pandas as pd

from src.annotation.classify_moves import MISTAKE_LABELS

VALUES = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 100}
SLIDERS = (chess.BISHOP, chess.ROOK, chess.QUEEN)
_ROOK_DIRS = [(1, 0), (-1, 0), (0, 1), (0, -1)]
_BISHOP_DIRS = [(1, 1), (1, -1), (-1, 1), (-1, -1)]


def _name(piece_type: chess.PieceType) -> str:
    return chess.piece_name(piece_type)


def _dirs(piece_type: chess.PieceType) -> list[tuple[int, int]]:
    if piece_type == chess.ROOK:
        return _ROOK_DIRS
    if piece_type == chess.BISHOP:
        return _BISHOP_DIRS
    if piece_type == chess.QUEEN:
        return _ROOK_DIRS + _BISHOP_DIRS
    return []


def _ray(square: chess.Square, df: int, dr: int):
    f, r = chess.square_file(square), chess.square_rank(square)
    while True:
        f, r = f + df, r + dr
        if not (0 <= f <= 7 and 0 <= r <= 7):
            return
        yield chess.square(f, r)


def _fork(board: chess.Board, sq: chess.Square, attacker: chess.Color) -> dict | None:
    piece = board.piece_at(sq)
    enemy = not attacker
    targets = []
    for t in board.attacks(sq):
        target = board.piece_at(t)
        if target is None or target.color != enemy or target.piece_type == chess.PAWN:
            continue
        valuable = target.piece_type == chess.KING or VALUES[target.piece_type] > VALUES[piece.piece_type]
        undefended = not board.is_attacked_by(enemy, t)
        if valuable or undefended:
            targets.append(t)
    if len(targets) < 2:
        return None
    return {"type": "fork", "piece": piece.piece_type, "square": sq,
            "targets": [(board.piece_at(t).piece_type, t) for t in targets]}


def _pin(board: chess.Board, before: chess.Board, sq: chess.Square, attacker: chess.Color) -> dict | None:
    piece = board.piece_at(sq)
    if piece.piece_type not in SLIDERS:
        return None
    enemy = not attacker
    for df, dr in _dirs(piece.piece_type):
        for t in _ray(sq, df, dr):
            target = board.piece_at(t)
            if target is None:
                continue
            if target.color == enemy and target.piece_type not in (chess.PAWN, chess.KING):
                if board.is_pinned(enemy, t) and not before.is_pinned(enemy, t):
                    return {"type": "pin", "piece": piece.piece_type, "square": sq,
                            "targets": [(target.piece_type, t)]}
            break
    return None


def _skewer(board: chess.Board, sq: chess.Square, attacker: chess.Color) -> dict | None:
    piece = board.piece_at(sq)
    if piece.piece_type not in SLIDERS:
        return None
    enemy = not attacker
    for df, dr in _dirs(piece.piece_type):
        seen = []
        for t in _ray(sq, df, dr):
            p = board.piece_at(t)
            if p is not None:
                seen.append((p, t))
                if len(seen) == 2:
                    break
        if len(seen) < 2:
            continue
        (front, f_sq), (back, b_sq) = seen
        if front.color != enemy or back.color != enemy:
            continue
        if front.piece_type not in (chess.KING, chess.QUEEN, chess.ROOK) or back.piece_type == chess.PAWN:
            continue
        if VALUES[front.piece_type] <= VALUES[back.piece_type]:
            continue
        if front.piece_type != chess.KING and VALUES[piece.piece_type] >= VALUES[front.piece_type]:
            continue  # attacking an equal/cheaper front piece is just a trade offer
        return {"type": "skewer", "piece": piece.piece_type, "square": sq,
                "targets": [(front.piece_type, f_sq), (back.piece_type, b_sq)]}
    return None


def motifs_created_by(board_before: chess.Board, move: chess.Move) -> list[dict]:
    """Input: board before the move, the move. Output: list of motif dicts the moved
    piece creates for the mover (order: fork, pin, skewer), possibly empty."""
    if move not in board_before.legal_moves:
        return []
    attacker = board_before.turn
    after = board_before.copy(stack=False)
    after.push(move)
    sq = move.to_square
    found = []
    for detector in (lambda: _fork(after, sq, attacker),
                     lambda: _pin(after, board_before, sq, attacker),
                     lambda: _skewer(after, sq, attacker)):
        motif = detector()
        if motif:
            found.append(motif)
    return found


def describe_motif(board_before: chess.Board, move: chess.Move, motif: dict) -> str:
    """Input: board before, the move, one motif dict. Output: plain-English clause such
    as 'Nf5 would have forked the queen on d6 and the rook on e7'."""
    san = board_before.san(move)
    targets = [f"the {_name(pt)} on {chess.square_name(s)}" for pt, s in motif["targets"]]
    if motif["type"] == "fork":
        return f"{san} would have forked {' and '.join(targets)}"
    if motif["type"] == "pin":
        return f"{san} would have pinned {targets[0]} to the king"
    return f"{san} would have skewered {targets[0]}, winning {targets[1]} behind it"


def add_motif_column(df: pd.DataFrame) -> pd.DataFrame:
    """Input: classified annotation DataFrame (fen, move_uci, best_move_uci, quality_label).
    Output: copy with 'motif' (motif type the engine's best move would have created and
    the played move did not, '' otherwise), 'motif_detail' (plain-English clause) and
    'missed_tactic' (bool: motif present AND the played move was a mistake or blunder)."""
    df = df.copy()
    motifs, details, missed = [], [], []
    for fen, played_uci, best_uci, label in zip(
        df.get("fen", []), df.get("move_uci", []), df.get("best_move_uci", []), df.get("quality_label", [])
    ):
        motif = detail = ""
        if best_uci and best_uci != played_uci:
            board = chess.Board(fen)
            best = chess.Move.from_uci(best_uci)
            best_motifs = motifs_created_by(board, best)
            if best_motifs:
                played_types = {m["type"] for m in motifs_created_by(board, chess.Move.from_uci(played_uci))}
                remaining = [m for m in best_motifs if m["type"] not in played_types]
                if remaining:
                    motif = remaining[0]["type"]
                    detail = describe_motif(board, best, remaining[0])
        motifs.append(motif)
        details.append(detail)
        missed.append(bool(motif) and label in MISTAKE_LABELS)
    df["motif"] = motifs
    df["motif_detail"] = details
    df["missed_tactic"] = missed
    return df
