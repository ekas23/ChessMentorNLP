"""Select and narrate concrete per-move instances of each persistent weakness,
from the existing annotated+featured move dataset — the 2026-09-22 change
request's "Personalized Training Plan with Game Examples" upgrade to Phase 5/6.

Data-model check (per the change request's explicit instruction to confirm
this before implementing, flagged here and in Memory.md rather than silently
fabricating): the per-move DataFrame already carries `fen` (the position
before the move) and `move_uci` (the move actually played) from Phase 2, and
`motif`/`pawn_structure`/`phase` from Phase 3 — enough to derive a real SAN
move string and a real evaluation swing for narration. What it did NOT carry
was *which* square/piece a detected motif applies to (fork/pin/skewer were
booleans only) — detect_fork/pin/skewer returned no such detail, so a
sentence like "you had a fork on f5" could not have been written truthfully.
That gap was closed with a small, additive Phase 3 extension
(features.motifs.describe_motifs(), new 'motif_detail' column) rather than
inventing square/piece specifics here. No new data collection was added: the
new column is derived from the same FEN already stored, via the same
board analysis detect_fork/pin/skewer already performed.
"""

import chess
import pandas as pd

from src.annotation.classify_moves import mover_loss_cp
from src.weakness.vectorize import MISTAKE_LABELS

MAX_INSTANCES_PER_WEAKNESS = 4

# metric name -> a filter over the moves DataFrame selecting candidate instance rows,
# mirroring the exact definitions weakness.vectorize.py uses to compute that metric's
# rate, so an "instance" is always a real contributor to the rate being narrated.
_QUALITY_LABEL_METRICS = {
    "blunder_rate": "blunder",
    "mistake_rate": "mistake",
    "inaccuracy_rate": "inaccuracy",
}
_PHASE_METRICS = {
    "opening_blunder_rate": "opening",
    "middlegame_blunder_rate": "middlegame",
    "endgame_blunder_rate": "endgame",
}


def filter_moves_for_metric(moves_df: pd.DataFrame, metric: str) -> pd.DataFrame:
    """Input shape: moves_df (the full annotated+featured per-move DataFrame),
    metric str (a weakness.aggregate.TREND_METRICS name, or a per-phase blunder-rate
    metric name).
    Output shape: pd.DataFrame, the subset of rows that are genuine contributors to
    that metric's rate (same definition weakness.vectorize.py uses to compute it).

    Purpose: the single source of "what counts as an instance of this weakness",
    shared by instance selection here so a shown example always matches the stat
    the card is about.
    """
    if metric in _QUALITY_LABEL_METRICS:
        return moves_df[moves_df["quality_label"] == _QUALITY_LABEL_METRICS[metric]]
    if metric in _PHASE_METRICS:
        phase = _PHASE_METRICS[metric]
        return moves_df[
            (moves_df["phase"] == phase) & (moves_df["quality_label"].isin(MISTAKE_LABELS))
        ]
    if metric == "missed_tactic_rate":
        return moves_df[(moves_df["motif"] != "") & (moves_df["quality_label"].isin(MISTAKE_LABELS))]
    if metric == "pawn_weakness_rate":
        return moves_df[moves_df["pawn_structure"] != "normal"]
    return moves_df.iloc[0:0]  # unknown metric -> no instances, never a guess


def _explainability_score(row: pd.Series) -> int:
    """Input shape: pandas.Series, one row of moves_df.
    Output shape: int, higher = easier to narrate clearly in one plain-language
    sentence without needing a deep engine line to justify it.

    Purpose: implements the change request's "prefer instances that are clear and
    explainable... a fork or hanging piece is easy to narrate; a 6-move
    advantage-conversion miss is not." A detected motif (fork/pin/skewer) is the
    clearest case — there's a concrete tactical pattern to name. A blunder-sized
    swing with no motif is still simple ("a piece was left hanging"-scale loss).
    A mistake/inaccuracy with no motif is the least self-explanatory case.
    """
    if row.get("motif_detail"):
        return 3
    if row.get("quality_label") == "blunder":
        return 2
    return 1


def _move_san(fen_before: str, move_uci: str) -> str | None:
    """Input shape: fen_before str (position before the move), move_uci str.
    Output shape: str | None, the move in standard algebraic notation, or None if
    it can't be derived (should not happen for well-formed annotated data, but
    this is presentation code — never let a formatting failure crash instance
    narration for an otherwise-valid weakness).

    Purpose: annotated data stores moves as UCI (engine.py's format); narration
    should read the way a human coach would write it, e.g. "Nf5" not "g3f5".
    """
    try:
        board = chess.Board(fen_before)
        return board.san(chess.Move.from_uci(move_uci))
    except (ValueError, AssertionError):
        return None


def _narrate_instance(row: pd.Series, metric: str, game_number: int) -> str:
    """Input shape: row (pandas.Series, one candidate move row), metric str,
    game_number int (the 1-indexed position of this game in the chronological
    timeline, matching the dashboard's "Per-Game Weakness Vector" table).
    Output shape: str, one plain-language sentence — matter-of-fact and
    encouraging in tone, per the change request, never just "you blundered."

    Purpose: turn one annotated move row into the "what happened and why it
    mattered" explanation required by the change request, grounded entirely in
    already-computed columns (quality_label, motif_detail, phase, pawn_structure,
    eval swing) -- no invented specifics.
    """
    move_san = _move_san(row["fen"], row["move_uci"]) or row["move_uci"]
    swing = abs(mover_loss_cp(row["fen"], row["eval_before"], row["eval_after"]))
    motif_detail = row.get("motif_detail") or ""

    if metric == "pawn_weakness_rate":
        return (
            f"After {move_san}, your pawn structure had a {row['pawn_structure']} weakness "
            f"that persisted from this point in the game."
        )

    if motif_detail:
        return (
            f"You had {motif_detail} available here, but played {move_san} instead — "
            f"the evaluation swung by about {swing:.0f} centipawns against you as a result."
        )

    label = row["quality_label"]
    return (
        f"{move_san} was a {label} during the {row['phase']}, costing about "
        f"{swing:.0f} centipawns of evaluation."
    )


def select_instances(
    moves_df: pd.DataFrame,
    metric: str,
    game_number_by_id: dict,
    max_instances: int = MAX_INSTANCES_PER_WEAKNESS,
) -> list[dict]:
    """Input shape: moves_df (full annotated+featured per-move DataFrame),
    metric str, game_number_by_id dict[str, int] (game_id -> 1-indexed chronological
    position, so narration can say "Game 12" matching the dashboard's table),
    max_instances int (cap, default 4 per the change request).
    Output shape: list[dict], each {game_id, game_number, move_number, quality_label,
    motif, explanation}, at most one per distinct game where possible (spread across
    games, per the change request), ordered by explainability then by how far along
    the game they occurred.

    Purpose: the change request's core selection logic — pick 2-4 clear,
    representative, spread-out examples of a persistent weakness rather than every
    occurrence or an arbitrary sample.
    """
    candidates = filter_moves_for_metric(moves_df, metric).copy()
    if candidates.empty:
        return []

    candidates["_score"] = candidates.apply(_explainability_score, axis=1)
    candidates = candidates.sort_values(["_score", "move_number"], ascending=[False, True])

    selected_rows = []
    seen_game_ids: set = set()

    # First pass: at most one instance per game, so 4 examples mean 4 different
    # games (a genuine pattern), not 4 moves from one bad game.
    for _, row in candidates.iterrows():
        if len(selected_rows) >= max_instances:
            break
        if row["game_id"] in seen_game_ids:
            continue
        selected_rows.append(row)
        seen_game_ids.add(row["game_id"])

    # Second pass: only if too few distinct games had a qualifying instance to
    # reach max_instances -- fill remaining slots from whatever is left.
    if len(selected_rows) < max_instances:
        for _, row in candidates.iterrows():
            if len(selected_rows) >= max_instances:
                break
            already_selected = any(
                row["game_id"] == s["game_id"] and row["move_number"] == s["move_number"]
                for s in selected_rows
            )
            if not already_selected:
                selected_rows.append(row)

    instances = []
    for row in selected_rows:
        game_number = game_number_by_id.get(row["game_id"])
        instances.append(
            {
                "game_id": row["game_id"],
                "game_number": game_number,
                "move_number": int(row["move_number"]),
                "quality_label": row["quality_label"],
                "motif": row.get("motif") or "",
                "phase": row.get("phase"),
                "metric": metric,
                "explanation": _narrate_instance(row, metric, game_number),
            }
        )
    return instances


def build_instances_by_weakness(
    moves_df: pd.DataFrame,
    trend_df: pd.DataFrame,
    persistent_weaknesses: list[str],
    max_instances: int = MAX_INSTANCES_PER_WEAKNESS,
) -> dict[str, list[dict]]:
    """Input shape: moves_df (full annotated+featured per-move DataFrame), trend_df
    (chronologically-sorted weakness-vector DataFrame, used only to build the
    game_id -> display-number mapping), persistent_weaknesses list[str] (from
    weakness.aggregate.identify_persistent_weaknesses — NOT recomputed here, per
    the change request's "do not change which weaknesses are classified as
    persistent"), max_instances int.
    Output shape: dict[str, list[dict]], weakness metric name -> its selected
    instances (see select_instances()). Only metrics in `persistent_weaknesses`
    get an entry — a one-off/non-persistent weakness gets no card, same as before
    this change (per the change request's explicit "what not to change").

    Purpose: the single entry point the report generator and recommender call to
    get per-instance, per-weakness example data.
    """
    game_number_by_id = {game_id: i + 1 for i, game_id in enumerate(trend_df["game_id"])}
    return {
        metric: select_instances(moves_df, metric, game_number_by_id, max_instances)
        for metric in persistent_weaknesses
    }
