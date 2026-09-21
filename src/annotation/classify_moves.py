"""Eval swing -> move quality label (blunder / mistake / inaccuracy / good).

Thresholds follow the common centipawn-loss convention used by Lichess/Chess.com
style analysis (a judgment call not specified in the project docs; recorded here
and in Memory.md per Rules.md §3):
  >= 200 cp loss -> blunder
  >= 100 cp loss -> mistake
  >=  50 cp loss -> inaccuracy
  <   50 cp loss -> good
"""

import pandas as pd

BLUNDER_THRESHOLD_CP = 200
MISTAKE_THRESHOLD_CP = 100
INACCURACY_THRESHOLD_CP = 50

QUALITY_LABELS = ["blunder", "mistake", "inaccuracy", "good"]


def mover_loss_cp(fen_before: str, eval_before: float, eval_after: float) -> float:
    """Input shape: fen_before str (position before the move, used only to determine
    which side moved, via its side-to-move field), eval_before/eval_after floats
    (centipawns, White's perspective, as produced by engine.evaluate_fen).
    Output shape: float, centipawn evaluation swing from the mover's own perspective
    (positive = the position got worse for the player who made the move).

    Purpose: shared "how much did this move cost, from the mover's point of view"
    calculation, used by classify_move() to pick a quality label and by
    nlp.instances' narration (2026-09-22 change request) to state a concrete
    swing size for a specific instance -- one calculation, not two that could drift.
    """
    mover_is_white = fen_before.split(" ")[1] == "w"
    before_for_mover = eval_before if mover_is_white else -eval_before
    after_for_mover = eval_after if mover_is_white else -eval_after
    return before_for_mover - after_for_mover


def classify_move(fen_before: str, eval_before: float, eval_after: float) -> str:
    """Input shape: fen_before str (position before the move, used only to determine
    which side moved, via its side-to-move field), eval_before/eval_after floats
    (centipawns, White's perspective, as produced by engine.evaluate_fen).
    Output shape: str, one of QUALITY_LABELS.

    Purpose: classify a single move by how much its own evaluation dropped, from
    the perspective of the player who made the move (so a move that worsens
    Black's position is scored the same way a move that worsens White's is).
    """
    loss = mover_loss_cp(fen_before, eval_before, eval_after)

    if loss >= BLUNDER_THRESHOLD_CP:
        return "blunder"
    if loss >= MISTAKE_THRESHOLD_CP:
        return "mistake"
    if loss >= INACCURACY_THRESHOLD_CP:
        return "inaccuracy"
    return "good"


def classify_moves_df(df: pd.DataFrame) -> pd.DataFrame:
    """Input shape: pd.DataFrame with at least {fen, eval_before, eval_after} columns.
    Output shape: the same DataFrame (copy) with a new 'quality_label' column.

    Purpose: row-wise wrapper applying classify_move() across an annotated-moves
    DataFrame, producing the full Annotation->Features contract shape.
    """
    df = df.copy()
    if df.empty:
        df["quality_label"] = pd.Series(dtype="object")
        return df
    df["quality_label"] = df.apply(
        lambda row: classify_move(row["fen"], row["eval_before"], row["eval_after"]), axis=1
    )
    return df
