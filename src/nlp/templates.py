"""Deterministic move-to-text templating (Phase 5A baseline).

Also provides template_report(), the always-available fallback used by
report_generator.generate_coaching_report() whenever the LLM path (Phase 5B)
is unavailable or fails — so a coherent report is guaranteed regardless of
external API availability.
"""

import pandas as pd

_METRIC_LABELS = {
    "blunder_rate": "blunders",
    "mistake_rate": "mistakes",
    "inaccuracy_rate": "inaccuracies",
    "pawn_weakness_rate": "weak pawn structures (isolated or doubled pawns)",
    "missed_tactic_rate": "missed tactical opportunities (forks, pins, or skewers)",
}


def move_to_text(move_row: dict) -> str:
    """Input shape: dict or pandas.Series with keys move_number, move_uci, quality_label,
    phase, and optionally motif.
    Output shape: str, one plain-language sentence describing that move.

    Purpose: the smallest unit of move-to-text templating required by Phases.md
    Phase 5 — deterministic, no external calls.
    """
    label = move_row["quality_label"]
    move_desc = f"move {move_row['move_number']} ({move_row['move_uci']})"
    if label == "good":
        sentence = f"On {move_desc}, a solid move was played."
    else:
        sentence = f"On {move_desc}, a {label} was played during the {move_row['phase']}."

    motif = move_row.get("motif") or ""
    if motif:
        sentence += f" A {motif.replace(',', '/')} pattern was present in this position."
    return sentence


def weakness_summary_sentence(metric: str, value: float) -> str:
    """Input shape: metric str (an aggregate.TREND_METRICS name), value float (a rate in
    [0, 1], typically the metric's latest EWM value).
    Output shape: str, one plain-language sentence about that weakness.

    Purpose: deterministic per-metric summary sentence, the building block of
    template_report().
    """
    label = _METRIC_LABELS.get(metric, metric)
    percent = round(value * 100)
    return f"Across recent games, {percent}% of moves involved {label}."


def template_report(vector_df: pd.DataFrame, ranked_weakness_tags: list[str], player_name: str) -> str:
    """Input shape: vector_df (trend-augmented weakness-vector DataFrame, chronologically
    sorted), ranked_weakness_tags list[str] (from weakness.aggregate.rank_weakness_tags),
    player_name str.
    Output shape: str, a deterministic multi-paragraph coaching report.

    Purpose: the Phase 5A baseline report, and the guaranteed fallback for Phase 5B —
    always produces a coherent, non-empty report from the computed data alone, with
    no external dependency.
    """
    games_analyzed = len(vector_df)
    intro = (
        f"Coaching Report for {player_name}\n\n"
        f"This report analyzes {games_analyzed} recent game"
        f"{'s' if games_analyzed != 1 else ''} in chronological order."
    )

    if not ranked_weakness_tags or vector_df.empty:
        body = "No clear recurring weakness pattern has been identified yet across this game history."
    else:
        latest = vector_df.iloc[-1]
        sentences = []
        for metric in ranked_weakness_tags[:3]:
            ewm_col = f"{metric}_ewm"
            value = latest[ewm_col] if ewm_col in vector_df.columns else latest.get(metric, 0.0)
            sentences.append(weakness_summary_sentence(metric, value))
        body = "The most significant recurring weaknesses identified are:\n" + "\n".join(
            f"- {s}" for s in sentences
        )

    closing = (
        "These patterns were identified by tracking rate-based weakness signals across your "
        "game history with an exponentially weighted trend, which favors recent games while "
        "still smoothing out any single unusually good or bad performance."
    )
    return f"{intro}\n\n{body}\n\n{closing}"
