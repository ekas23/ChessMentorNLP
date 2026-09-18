"""Longitudinal (rolling/EWM) weakness trend tracking across a chronological
batch of games — the layer that distinguishes a transient mistake from a
persistent weakness (PRD.md's core problem statement).
"""

import pandas as pd

TREND_METRICS = [
    "blunder_rate",
    "mistake_rate",
    "inaccuracy_rate",
    "pawn_weakness_rate",
    "missed_tactic_rate",
]

# Judgment calls (not specified in project docs), documented in Memory.md:
DEFAULT_ROLLING_WINDOW = 5
DEFAULT_EWM_SPAN = 5
DEFAULT_MIN_GAMES_FOR_PERSISTENCE = 3
DEFAULT_PERSISTENCE_THRESHOLD = 0.15


def sort_chronologically(vector_df: pd.DataFrame) -> pd.DataFrame:
    """Input shape: pd.DataFrame with a 'date' column (raw PGN Date header strings,
    e.g. "2026.01.01", possibly with "??" placeholders for an unknown day/month).
    Output shape: copy of vector_df sorted ascending by parsed date (rows with an
    unparseable/missing date are placed last, in their original relative order).

    Purpose: the rolling/EWM trend functions below assume row order == chronological
    game order; this guarantees that regardless of what order games/games were fetched in.
    """
    df = vector_df.copy()
    parsed_dates = pd.to_datetime(df["date"], format="%Y.%m.%d", errors="coerce")
    df = df.assign(_parsed_date=parsed_dates)
    df = df.sort_values("_parsed_date", kind="stable", na_position="last")
    return df.drop(columns="_parsed_date").reset_index(drop=True)


def add_rolling_trends(
    vector_df: pd.DataFrame,
    window: int = DEFAULT_ROLLING_WINDOW,
    ewm_span: int = DEFAULT_EWM_SPAN,
) -> pd.DataFrame:
    """Input shape: chronologically-sorted weakness-vector DataFrame (output of
    vectorize.vectorize_games() + sort_chronologically()).
    Output shape: copy with, for every metric in TREND_METRICS present in vector_df,
    two new columns: '{metric}_rolling' (simple trailing rolling mean, min_periods=1)
    and '{metric}_ewm' (exponentially weighted mean, span=ewm_span).

    Purpose: build the trend columns required by Architecture.md §4's Weakness->NLP
    contract. The EWM column is the primary trend signal (see
    identify_persistent_weaknesses) because it weights recent games more heavily
    without needing a hard window-size cutoff, so it adapts as new games arrive
    while still smoothing out a single bad game.
    """
    df = vector_df.copy()
    for metric in TREND_METRICS:
        if metric not in df.columns:
            continue
        df[f"{metric}_rolling"] = df[metric].rolling(window=window, min_periods=1).mean()
        df[f"{metric}_ewm"] = df[metric].ewm(span=ewm_span, adjust=False).mean()
    return df


def identify_persistent_weaknesses(
    trend_df: pd.DataFrame,
    min_games: int = DEFAULT_MIN_GAMES_FOR_PERSISTENCE,
    threshold: float = DEFAULT_PERSISTENCE_THRESHOLD,
) -> list[str]:
    """Input shape: trend_df (output of add_rolling_trends(), chronologically sorted),
    min_games int (games required before a trend counts as persistent rather than noise),
    threshold float (EWM rate above which a weakness is considered elevated).
    Output shape: list[str] of metric names (from TREND_METRICS) whose EWM trend has
    stayed above `threshold` for every one of the most recent `min_games` games.

    Purpose: the core "transient vs. persistent" distinction from PRD.md — a metric
    that spiked once and dropped back down does not qualify; only a weakness that has
    stayed elevated across the recent window is flagged as persistent. Returns an
    empty list (not an error) when there isn't yet enough game history to judge.
    """
    if len(trend_df) < min_games:
        return []

    persistent = []
    for metric in TREND_METRICS:
        ewm_col = f"{metric}_ewm"
        if ewm_col not in trend_df.columns:
            continue
        recent_values = trend_df[ewm_col].tail(min_games)
        if (recent_values > threshold).all():
            persistent.append(metric)
    return persistent


def rank_weakness_tags(
    trend_df: pd.DataFrame, persistent_weaknesses: list[str] | None = None
) -> list[str]:
    """Input shape: trend_df (output of add_rolling_trends(), chronologically sorted),
    persistent_weaknesses optional list[str] (output of identify_persistent_weaknesses();
    computed with default thresholds if omitted).
    Output shape: list[str] of metric names, most severe first.

    Purpose: the ranked weakness-tag list required by Architecture.md §4's
    NLP->Recommendation contract. Persistent weaknesses are ranked first (by their
    most recent EWM value, highest first), followed by any other tracked metrics
    also ranked by most recent EWM value — so a report/recommendation always has a
    full ranking to draw on, not just the (possibly empty) persistent subset.
    """
    if trend_df.empty:
        return []
    if persistent_weaknesses is None:
        persistent_weaknesses = identify_persistent_weaknesses(trend_df)

    latest = trend_df.iloc[-1]

    def latest_ewm(metric: str) -> float:
        col = f"{metric}_ewm"
        return latest[col] if col in trend_df.columns else 0.0

    persistent_sorted = sorted(persistent_weaknesses, key=latest_ewm, reverse=True)
    remaining = [
        m for m in TREND_METRICS if m not in persistent_weaknesses and f"{m}_ewm" in trend_df.columns
    ]
    remaining_sorted = sorted(remaining, key=latest_ewm, reverse=True)
    return persistent_sorted + remaining_sorted
