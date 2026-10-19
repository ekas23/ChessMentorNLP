"""Longitudinal trends and the persistence test.

For each metric k and game t (chronological), x[t,k] is the per-game rate from
vectorize.py and s[t,k] its exponentially weighted moving average
    s[t,k] = a * x[t,k] + (1 - a) * s[t-1,k],   a = 2 / (span + 1), span = 10.

Metric k is PERSISTENT when all three hold:
  (1) level:     s[N,k] >= TAU[k]                      (recently elevated)
  (2) frequency: share of games with x[t,k] > 0 >= RHO (shows up often)
  (3) spread:    it occurs in both the first and second half of the history
                 (one bad week cannot produce a flag on its own)
and at least MIN_GAMES games were analysed. TAU values are per-move rates and are
starting defaults meant to be calibrated on a cohort (RQ3, docs/EVALUATION.md);
they are deliberately exposed as parameters rather than hard-coded in callers.
"""

from __future__ import annotations

import pandas as pd

TREND_METRICS = [
    "blunder_rate",
    "mistake_rate",
    "inaccuracy_rate",
    "missed_tactic_rate",
    "pawn_weakness_rate",
]

DEFAULT_EWM_SPAN = 10
DEFAULT_ROLLING_WINDOW = 5
MIN_GAMES = 10
RHO = 0.3
TAU = {
    "blunder_rate": 0.03,
    "mistake_rate": 0.04,
    "inaccuracy_rate": 0.08,
    "missed_tactic_rate": 0.015,
    "pawn_weakness_rate": 0.015,
}


def sort_chronologically(vector_df: pd.DataFrame) -> pd.DataFrame:
    """Input: weakness vectors with a PGN 'date' column. Output: copy sorted by date
    (stable, so same-day games keep their fetched order; unparseable dates last)."""
    df = vector_df.copy()
    df["_d"] = pd.to_datetime(df["date"], format="%Y.%m.%d", errors="coerce")
    df = df.sort_values("_d", kind="stable", na_position="last").drop(columns="_d")
    return df.reset_index(drop=True)


def add_rolling_trends(
    vector_df: pd.DataFrame, window: int = DEFAULT_ROLLING_WINDOW, ewm_span: int = DEFAULT_EWM_SPAN
) -> pd.DataFrame:
    """Input: chronologically sorted vectors. Output: copy with '{metric}_rolling' and
    '{metric}_ewm' columns for every tracked metric."""
    df = vector_df.copy()
    for metric in TREND_METRICS:
        if metric in df.columns:
            df[f"{metric}_rolling"] = df[metric].rolling(window=window, min_periods=1).mean()
            df[f"{metric}_ewm"] = df[metric].ewm(span=ewm_span, adjust=False).mean()
    return df


def persistence_diagnostics(
    trend_df: pd.DataFrame, tau: dict | None = None, rho: float = RHO, min_games: int = MIN_GAMES
) -> dict[str, dict]:
    """Input: trend DataFrame (add_rolling_trends output), thresholds.
    Output: {metric: {ewm, tau, presence, rho, first_half, second_half, persistent}}.

    Purpose: compute the persistence test AND keep the evidence for each decision, so
    the report can say why something was or wasn't flagged, and so the evaluation
    scripts can re-run the exact same test on subsets (e.g. split halves)."""
    tau = {**TAU, **(tau or {})}
    n = len(trend_df)
    out: dict[str, dict] = {}
    for metric in TREND_METRICS:
        if metric not in trend_df.columns or n == 0:
            continue
        values = trend_df[metric].fillna(0.0)
        ewm_col = f"{metric}_ewm"
        ewm = float(trend_df[ewm_col].iloc[-1]) if ewm_col in trend_df.columns else float(values.mean())
        half = n // 2
        first = bool((values.iloc[:half] > 0).any()) if half else False
        second = bool((values.iloc[half:] > 0).any())
        presence = float((values > 0).mean())
        persistent = n >= min_games and ewm >= tau[metric] and presence >= rho and first and second
        out[metric] = {
            "ewm": ewm, "tau": tau[metric], "presence": presence, "rho": rho,
            "first_half": first, "second_half": second, "games": n, "persistent": persistent,
        }
    return out


def identify_persistent_weaknesses(trend_df: pd.DataFrame, **kwargs) -> list[str]:
    """Input: trend DataFrame (+ optional tau/rho/min_games). Output: persistent metric
    names, most severe first (by EWM relative to its threshold)."""
    diag = persistence_diagnostics(trend_df, **kwargs)
    flagged = [m for m, d in diag.items() if d["persistent"]]
    return sorted(flagged, key=lambda m: diag[m]["ewm"] / diag[m]["tau"], reverse=True)


def rank_weakness_tags(trend_df: pd.DataFrame, persistent_weaknesses: list[str] | None = None) -> list[str]:
    """Input: trend DataFrame, persistent list. Output: all tracked metrics, persistent
    first, then the rest ordered by EWM relative to their threshold."""
    if trend_df.empty:
        return []
    diag = persistence_diagnostics(trend_df)
    if persistent_weaknesses is None:
        persistent_weaknesses = identify_persistent_weaknesses(trend_df)
    rest = sorted((m for m in diag if m not in persistent_weaknesses),
                  key=lambda m: diag[m]["ewm"] / diag[m]["tau"], reverse=True)
    return list(persistent_weaknesses) + rest
