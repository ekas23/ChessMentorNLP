"""Select and narrate concrete instances of each persistent weakness.

Fixes vs. the previous version (2026-10-19):
  * Each card only draws from rows that count towards ITS metric (the blunder
    card used to be filled with skewer misses because any row carrying a motif
    was preferred, whatever card it was on).
  * Only the analysed player's moves are candidates.
  * "move N" is the full-move number as printed in the PGN ("17. Nf5" /
    "17... Nf5"), not a half-move counter.
  * Every instance carries the game's date/opponent/link and a link that opens
    the exact position on Lichess, so the player can find and replay it.
  * Wording is built from complete sentences, so no stray capitals mid-sentence.
"""

from __future__ import annotations

import chess
import pandas as pd

from src.annotation.classify_moves import MISTAKE_LABELS, win_chance
from src.weakness.vectorize import is_pawn_weakness, player_moves

MAX_INSTANCES_PER_WEAKNESS = 4
LICHESS_ANALYSIS_URL = "https://lichess.org/analysis/standard/{fen}?color={color}"

_LABEL_METRICS = {"blunder_rate": "blunder", "mistake_rate": "mistake", "inaccuracy_rate": "inaccuracy"}
_PHASE_METRICS = {"opening_blunder_rate": "opening", "middlegame_blunder_rate": "middlegame",
                  "endgame_blunder_rate": "endgame"}


def filter_moves_for_metric(moves_df: pd.DataFrame, metric: str) -> pd.DataFrame:
    """Input: all move rows, a metric name. Output: the player's rows that count towards
    that metric -- the same definition vectorize.py uses to compute its rate."""
    mine = player_moves(moves_df)
    if metric in _LABEL_METRICS:
        return mine[mine["quality_label"] == _LABEL_METRICS[metric]]
    if metric in _PHASE_METRICS:
        return mine[(mine["phase"] == _PHASE_METRICS[metric]) & mine["quality_label"].isin(MISTAKE_LABELS)]
    if metric == "missed_tactic_rate":
        return mine[mine["missed_tactic"].astype(bool)]
    if metric == "pawn_weakness_rate":
        return mine[is_pawn_weakness(mine)]
    return mine.iloc[0:0]


def _san(fen: str, uci: str | None) -> str | None:
    if not uci:
        return None
    try:
        board = chess.Board(fen)
        return board.san(chess.Move.from_uci(uci))
    except (ValueError, AssertionError):
        return None


def _win_pct(side: str, cp: float) -> int:
    sign = 1 if side == "white" else -1
    return round((win_chance(sign * cp) + 1) / 2 * 100)


def _hanging_piece(row: pd.Series) -> str | None:
    """If the opponent's best reply captures one of the player's pieces, describe it."""
    reply = row.get("best_reply_uci")
    if not reply:
        return None
    board = chess.Board(row["fen"])
    board.push(chess.Move.from_uci(row["move_uci"]))
    move = chess.Move.from_uci(reply)
    if move not in board.legal_moves or not board.is_capture(move):
        return None
    captured = board.piece_at(move.to_square)
    piece = "pawn" if captured is None else chess.piece_name(captured.piece_type)
    if piece == "pawn":
        return None  # losing a pawn is rarely what made a move a blunder
    reply_san = board.san(move)
    return f"It left your {piece} on {chess.square_name(move.to_square)} to be taken by {reply_san}."


def move_label(row: pd.Series) -> str:
    """'17. Nf5' for White, '17... Nf5' for Black."""
    dots = "." if row["side"] == "white" else "..."
    return f"{int(row['move_number'])}{dots} {row['move_san']}"


def narrate_instance(row: pd.Series, metric: str) -> str:
    """Input: one move row, the metric it illustrates. Output: 1-3 plain sentences built
    only from computed columns (never invented details)."""
    before, after = _win_pct(row["side"], row["eval_before"]), _win_pct(row["side"], row["eval_after"])
    swing = f"Your winning chances went from {before}% to {after}%."
    best_san = _san(row["fen"], row.get("best_move_uci"))
    prefer = f" The engine preferred {best_san}." if best_san and best_san != row["move_san"] else ""

    if metric == "missed_tactic_rate" and row.get("motif_detail"):
        detail = row["motif_detail"][0].upper() + row["motif_detail"][1:]
        return f"{detail}. You played {row['move_san']} instead. {swing}"
    if metric == "pawn_weakness_rate":
        return f"{row['move_san']} gave you {row['pawn_weakness_created']}.{prefer} {swing}"
    if row["quality_label"] == "blunder":
        hanging = _hanging_piece(row)
        lead = hanging if hanging else f"{row['move_san']} was a blunder."
        return f"{lead}{prefer} {swing}"
    article = "an" if row["quality_label"][0] in "aeiou" else "a"
    return f"{row['move_san']} was {article} {row['quality_label']} in the {row['phase']}.{prefer} {swing}"


def _explainability(row: pd.Series, metric: str) -> int:
    if metric == "blunder_rate" and _hanging_piece(row):
        return 2  # "you left your knight hanging" is the easiest lesson to show
    if metric == "missed_tactic_rate" and row.get("motif") == "fork":
        return 1
    return 0


def select_instances(
    moves_df: pd.DataFrame, metric: str, game_info: dict[str, dict], max_instances: int = MAX_INSTANCES_PER_WEAKNESS
) -> list[dict]:
    """Input: move rows, metric, {game_id: {number, date, opponent, link, colour}}, cap.
    Output: up to max_instances instance dicts, at most one per game while possible,
    clearest and most costly first."""
    candidates = filter_moves_for_metric(moves_df, metric)
    candidates = candidates[candidates["game_id"].isin(game_info)]
    if candidates.empty:
        return []
    candidates = candidates.assign(
        _explain=[_explainability(r, metric) for _, r in candidates.iterrows()]
    ).sort_values(["_explain", "wc_drop"], ascending=[False, False])

    chosen, seen = [], set()
    for _, row in candidates.iterrows():
        if row["game_id"] not in seen:
            chosen.append(row)
            seen.add(row["game_id"])
        if len(chosen) >= max_instances:
            break
    if len(chosen) < max_instances:
        picked = {(r["game_id"], r["ply"]) for r in chosen}
        for _, row in candidates.iterrows():
            if len(chosen) >= max_instances:
                break
            if (row["game_id"], row["ply"]) not in picked:
                chosen.append(row)

    instances = []
    for row in chosen:
        info = game_info[row["game_id"]]
        instances.append({
            "game_id": row["game_id"],
            "game_number": info["number"],
            "date": info.get("date"),
            "opponent": info.get("opponent"),
            "game_link": info.get("link"),
            "move_number": int(row["move_number"]),
            "move_label": move_label(row),
            "quality_label": row["quality_label"],
            "motif": row.get("motif") or "",
            "phase": row.get("phase"),
            "metric": metric,
            "explanation": narrate_instance(row, metric),
            "position_url": LICHESS_ANALYSIS_URL.format(fen=row["fen"].replace(" ", "_"), color=row["side"]),
        })
    return instances


def game_info_from_trend(trend_df: pd.DataFrame) -> dict[str, dict]:
    """Input: chronological trend DataFrame. Output: {game_id: display info} where
    'number' matches the row number in the dashboard's per-game table."""
    info = {}
    for i, row in enumerate(trend_df.to_dict(orient="records"), start=1):
        info[row["game_id"]] = {"number": i, "date": row.get("date"), "opponent": row.get("opponent"),
                                "link": row.get("link"), "colour": row.get("colour")}
    return info


def build_instances_by_weakness(
    moves_df: pd.DataFrame, trend_df: pd.DataFrame, persistent_weaknesses: list[str],
    max_instances: int = MAX_INSTANCES_PER_WEAKNESS,
) -> dict[str, list[dict]]:
    """Input: move rows, trend DataFrame, persistent metric names.
    Output: {metric: instances} for persistent metrics only."""
    info = game_info_from_trend(trend_df)
    return {m: select_instances(moves_df, m, info, max_instances) for m in persistent_weaknesses}
