"""Move quality labels from the drop in winning chances (Lichess's method).

A raw centipawn threshold mislabels moves in decided positions: going from +900
to +600 is "300 cp lost" but the game is still completely won. Lichess instead
converts each evaluation to winning chances in [-1, 1]

    wc(cp) = 2 / (1 + exp(-0.00368208 * cp)) - 1

and labels a move by how much the mover's winning chances fell:
    drop >= 0.3 -> blunder, >= 0.2 -> mistake, >= 0.1 -> inaccuracy, else good.
(Constants from Lichess's open-source analysis code; documented in Memory.md.)

Evaluations arrive in centipawns from White's point of view; every quantity
here is converted to the mover's point of view first.
"""

from __future__ import annotations

import math

import pandas as pd

WIN_CHANCE_K = 0.00368208
BLUNDER_DROP = 0.3
MISTAKE_DROP = 0.2
INACCURACY_DROP = 0.1

QUALITY_LABELS = ["blunder", "mistake", "inaccuracy", "good"]
MISTAKE_LABELS = ["blunder", "mistake"]


def win_chance(cp: float) -> float:
    """Input: centipawns (any POV). Output: winning chances in [-1, 1] for that POV."""
    return 2.0 / (1.0 + math.exp(-WIN_CHANCE_K * cp)) - 1.0


def _mover_sign(side: str) -> int:
    return 1 if side == "white" else -1


def mover_loss_cp(side: str, eval_before: float, eval_after: float) -> float:
    """Input: side that moved ('white'|'black'), evals in White-POV cp.
    Output: centipawns the mover lost with this move (positive = worse for the mover)."""
    s = _mover_sign(side)
    return s * eval_before - s * eval_after


def win_chance_drop(side: str, eval_before: float, eval_after: float) -> float:
    """Input: as mover_loss_cp. Output: drop in the mover's winning chances, in [-2, 2]."""
    s = _mover_sign(side)
    return win_chance(s * eval_before) - win_chance(s * eval_after)


def classify_move(side: str, eval_before: float, eval_after: float) -> str:
    """Input: side, White-POV evals. Output: one of QUALITY_LABELS."""
    drop = win_chance_drop(side, eval_before, eval_after)
    if drop >= BLUNDER_DROP:
        return "blunder"
    if drop >= MISTAKE_DROP:
        return "mistake"
    if drop >= INACCURACY_DROP:
        return "inaccuracy"
    return "good"


def classify_moves_df(df: pd.DataFrame) -> pd.DataFrame:
    """Input: annotation DataFrame with side, eval_before, eval_after.
    Output: copy with cp_loss, wc_drop, quality_label columns."""
    df = df.copy()
    if df.empty:
        for col, dtype in (("cp_loss", "float"), ("wc_drop", "float"), ("quality_label", "object")):
            df[col] = pd.Series(dtype=dtype)
        return df
    df["cp_loss"] = [mover_loss_cp(s, b, a) for s, b, a in zip(df["side"], df["eval_before"], df["eval_after"])]
    df["wc_drop"] = [win_chance_drop(s, b, a) for s, b, a in zip(df["side"], df["eval_before"], df["eval_after"])]
    labels = [classify_move(s, b, a) for s, b, a in zip(df["side"], df["eval_before"], df["eval_after"])]
    if "best_move_uci" in df.columns:
        # Playing the engine's own top choice is never an error. An apparent drop then
        # only reflects search noise between two fixed-depth searches.
        labels = ["good" if played == best else label
                  for label, played, best in zip(labels, df["move_uci"], df["best_move_uci"])]
    df["quality_label"] = labels
    return df
