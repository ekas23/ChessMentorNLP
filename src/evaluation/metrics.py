"""Evaluation metrics for the paper (docs/EVALUATION.md): annotation agreement (RQ1),
split-half persistence stability (RQ2)."""

from __future__ import annotations

from collections import Counter

import pandas as pd

from src.weakness.aggregate import TREND_METRICS, add_rolling_trends, persistence_diagnostics


def cohen_kappa(a: list, b: list) -> float:
    """Input: two equal-length label lists. Output: Cohen's kappa (1 = perfect agreement,
    0 = chance level). Returns 1.0 when both raters use a single identical label."""
    if len(a) != len(b) or not a:
        raise ValueError("need two non-empty label lists of equal length")
    n = len(a)
    observed = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    expected = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / (n * n)
    return 1.0 if expected == 1 else (observed - expected) / (1 - expected)


def split_half_agreement(trend_df: pd.DataFrame, min_games: int = 5) -> dict:
    """Input: a player's chronological weakness vectors (vectorize output, any trend
    columns are recomputed). Output: {'first': [...], 'second': [...], 'agreement':
    share of tracked metrics with the same flag in both halves, 'jaccard': overlap of
    the two flagged sets (1.0 when both are empty)}.

    Purpose: RQ2. A stable persistence test should flag mostly the same weaknesses
    on the earlier and the later half of the same player's games."""
    base = trend_df[[c for c in trend_df.columns if not c.endswith(("_ewm", "_rolling"))]]
    half = len(base) // 2
    flags = []
    for part in (base.iloc[:half], base.iloc[half:]):
        diag = persistence_diagnostics(add_rolling_trends(part.reset_index(drop=True)), min_games=min_games)
        flags.append({m for m, d in diag.items() if d["persistent"]})
    first, second = flags
    tracked = [m for m in TREND_METRICS if m in base.columns]
    agreement = sum((m in first) == (m in second) for m in tracked) / len(tracked) if tracked else float("nan")
    union = first | second
    return {"first": sorted(first), "second": sorted(second), "agreement": agreement,
            "jaccard": 1.0 if not union else len(first & second) / len(union)}
