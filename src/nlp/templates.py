"""Deterministic report text (the default report, and the LLM path's fallback).

Also provides baseline_report(): a statistics-only report with no persistence
test and no game examples. It exists for the user study (RQ4 in
docs/EVALUATION.md), which compares the grounded report against it.
"""

from __future__ import annotations

import pandas as pd

METRIC_LABELS = {
    "blunder_rate": "Blunders",
    "mistake_rate": "Mistakes",
    "inaccuracy_rate": "Inaccuracies",
    "missed_tactic_rate": "Missed tactics",
    "pawn_weakness_rate": "Pawn-structure concessions",
    "opening_blunder_rate": "Opening errors",
    "middlegame_blunder_rate": "Middlegame errors",
    "endgame_blunder_rate": "Endgame errors",
}

_METRIC_WHAT = {
    "blunder_rate": "were blunders",
    "mistake_rate": "were mistakes",
    "inaccuracy_rate": "were inaccuracies",
    "missed_tactic_rate": "missed a fork, pin or skewer that the engine found",
    "pawn_weakness_rate": "created an isolated or doubled pawn that cost you",
}


def metric_label(metric: str) -> str:
    """Readable name for a metric key, e.g. 'missed_tactic_rate' -> 'Missed tactics'."""
    return METRIC_LABELS.get(metric, metric.replace("_", " ").capitalize())


def rate_phrase(rate: float) -> str:
    """0.021 -> '2.1% of your moves (about one in every 48)'."""
    if rate <= 0:
        return "none of your moves"
    every = max(1, round(1 / rate))
    return f"{rate * 100:.1f}% of your moves (about one in every {every})"


def instance_sentence(instance: dict) -> str:
    """One example as a full sentence, e.g. 'In game 12 (vs Bob, 2026.09.30), on 17. Rd1: ...'."""
    context = ", ".join(x for x in (f"vs {instance['opponent']}" if instance.get("opponent") else "",
                                    instance.get("date") or "") if x)
    where = f"In game {instance['game_number']}" + (f" ({context})" if context else "")
    return f"{where}, on {instance['move_label']}: {instance['explanation']}"


def _scope_sentence(games: int, time_class: str | None, skipped: int) -> str:
    tc = f" {time_class}" if time_class and time_class != "all" else ""
    s = f"This report covers your last {games}{tc} game{'s' if games != 1 else ''}, in the order you played them."
    if skipped:
        s += f" {skipped} very short game{'s were' if skipped != 1 else ' was'} left out, since a handful of moves says little."
    return s


def template_report(
    trend_df: pd.DataFrame,
    persistent: list[str],
    diagnostics: dict[str, dict],
    player_name: str,
    instances_by_weakness: dict[str, list[dict]] | None = None,
    time_class: str | None = None,
    skipped: int = 0,
) -> str:
    """Input: trend DataFrame, persistent metrics, persistence diagnostics, player name,
    instances, time-class filter used, number of games excluded as too short.
    Output: multi-paragraph plain-text report."""
    instances_by_weakness = instances_by_weakness or {}
    parts = [f"Coaching report for {player_name}", _scope_sentence(len(trend_df), time_class, skipped)]

    if not persistent:
        parts.append(
            "No weakness came up often enough, and consistently enough across your games, to count "
            "as a recurring pattern. That is good news. Analysing more games will make the picture clearer."
        )
    else:
        lines = ["These patterns keep coming back in your games:"]
        for metric in persistent:
            d = diagnostics[metric]
            lines.append(
                f"- {metric_label(metric)}: recently {rate_phrase(d['ewm'])} {_METRIC_WHAT.get(metric, '')}. "
                f"It happened in {d['presence'] * 100:.0f}% of your games, early and late in this stretch."
            )
        parts.append("\n".join(lines))

        examples = [instance_sentence(inst[0]) for m in persistent if (inst := instances_by_weakness.get(m))]
        if examples:
            parts.append("Here is where it shows up in your own games:\n" + "\n".join(f"- {e}" for e in examples)
                         + "\nThe training plan below has more examples and practice for each one.")

    not_flagged = [m for m, d in diagnostics.items()
                   if m not in persistent and not d["persistent"] and d["presence"] > 0]
    if not_flagged:
        names = ", ".join(metric_label(m).lower() for m in not_flagged)
        parts.append(
            f"Also tracked but not flagged: {names}. Each happened in some games but not often or "
            "consistently enough to call it a habit."
        )

    parts.append(
        "How this works: every one of your moves was checked by Stockfish. A weakness is only called "
        "a pattern when its recent rate is high, it appears in a good share of your games, and it shows "
        "up in both the earlier and the later half of the games analysed."
    )
    return "\n\n".join(parts)


def baseline_report(trend_df: pd.DataFrame, player_name: str) -> str:
    """Input: trend DataFrame, player name. Output: statistics-only report (no persistence
    test, no examples) -- the comparison condition for the user study."""
    lines = [f"Statistics for {player_name} ({len(trend_df)} games)"]
    for metric in ("blunder_rate", "mistake_rate", "inaccuracy_rate", "missed_tactic_rate", "pawn_weakness_rate"):
        if metric in trend_df.columns:
            lines.append(f"- {metric_label(metric)}: {trend_df[metric].mean() * 100:.1f}% of moves on average")
    lines.append("Practise tactics puzzles and review your games to reduce these numbers.")
    return "\n".join(lines)
