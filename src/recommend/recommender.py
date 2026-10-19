"""Weakness tag -> Lichess puzzle themes / opening study / endgame drill mapping.

Puzzle theme slugs below are real, documented Lichess puzzle-training theme
tags (https://lichess.org/training/themes) — used verbatim to build real
"https://lichess.org/training/{theme}" training links, per Rules.md's ban on
fabricating chess domain facts. Weaknesses that don't correspond to a Lichess
puzzle theme (e.g. pawn-structure quality, which Lichess doesn't tag as a
puzzle theme) are instead given a concrete study-note recommendation.
"""

import pandas as pd

LICHESS_TRAINING_URL = "https://lichess.org/training/{theme}"

# metric name -> (training_type, [lichess puzzle theme slugs] | None, description template)
_WEAKNESS_RECOMMENDATIONS: dict[str, dict] = {
    "blunder_rate": {
        "training_type": "puzzle",
        "puzzle_themes": ["hangingPiece", "advantage"],
        "description": "Blunders are the highest-priority fix. Drill hanging-piece and "
        "advantage-conversion puzzles to build the habit of double-checking each move for "
        "material safety before playing it.",
    },
    "mistake_rate": {
        "training_type": "puzzle",
        "puzzle_themes": ["advantage", "middlegame"],
        "description": "Mistakes usually come from missing a stronger continuation. "
        "Middlegame advantage-conversion puzzles build the calculation habit needed to spot them.",
    },
    "inaccuracy_rate": {
        "training_type": "puzzle",
        "puzzle_themes": ["advantage"],
        "description": "Inaccuracies are small but frequent evaluation drops. Regular "
        "advantage puzzles sharpen move selection under normal (non-critical) positions.",
    },
    "missed_tactic_rate": {
        "training_type": "puzzle",
        "puzzle_themes": ["fork", "pin", "skewer"],
        "description": "In these positions the engine's best move was a fork, pin or skewer, "
        "and a different move cost you. Puzzles on the exact motif you missed build the "
        "pattern recognition to spot it next time.",
    },
    "pawn_weakness_rate": {
        "training_type": "opening_study",
        "puzzle_themes": None,
        "description": "Your moves keep creating isolated or doubled pawns that the engine "
        "judged as costly. Before a pawn capture or exchange, check what it does to your "
        "pawn structure; study material on pawn structures helps more than puzzles here.",
    },
    "opening_blunder_rate": {
        "training_type": "opening_study",
        "puzzle_themes": ["opening"],
        "description": "Blunders are concentrated in the opening phase. Review your main "
        "opening lines for known traps, and use opening-phase puzzles to sharpen early-game "
        "calculation.",
    },
    "middlegame_blunder_rate": {
        "training_type": "puzzle",
        "puzzle_themes": ["middlegame"],
        "description": "Blunders are concentrated in the middlegame. Middlegame-tagged puzzles "
        "target exactly this phase.",
    },
    "endgame_blunder_rate": {
        "training_type": "endgame_drill",
        "puzzle_themes": ["endgame", "pawnEndgame", "rookEndgame"],
        "description": "Blunders are concentrated in the endgame. Drill basic endgame "
        "technique (pawn and rook endgames are the most common types) alongside endgame-tagged puzzles.",
    },
}


THEME_LABELS = {
    "fork": "fork", "pin": "pin", "skewer": "skewer", "hangingPiece": "hanging-piece",
    "advantage": "advantage", "opening": "opening", "middlegame": "middlegame",
    "endgame": "endgame", "pawnEndgame": "pawn-endgame", "rookEndgame": "rook-endgame",
}


def practice_link(theme: str) -> dict:
    """Input: a Lichess puzzle theme slug. Output: {'url', 'label'} for the UI, e.g.
    {'url': 'https://lichess.org/training/fork', 'label': 'Lichess fork puzzles'}."""
    return {"url": LICHESS_TRAINING_URL.format(theme=theme),
            "label": f"Lichess {THEME_LABELS.get(theme, theme)} puzzles"}


def match_puzzle_for_instance(instance: dict) -> list[dict]:
    """Input: one instance (nlp.instances). Output: practice links matched to what
    actually went wrong in that instance: the missed motif's theme for a missed tactic,
    hanging-piece puzzles for a blunder that left material en prise, the game phase
    otherwise. Pawn-structure instances get none (Lichess has no puzzle theme for it).

    These are theme pages, not a puzzle chosen to resemble the position -- the UI
    labels them accordingly."""
    metric = instance.get("metric")
    if metric == "pawn_weakness_rate":
        return []
    if metric == "missed_tactic_rate" and instance.get("motif"):
        return [practice_link(instance["motif"])]
    if instance.get("quality_label") == "blunder" and "to be taken" in instance.get("explanation", ""):
        return [practice_link("hangingPiece")]
    phase = instance.get("phase")
    if phase in ("opening", "middlegame", "endgame"):
        return [practice_link(phase)]
    return [practice_link("advantage")]


def recommend_for_weakness(metric: str, context: dict | None = None) -> dict:
    """Input shape: metric str (a weakness-vector metric name, e.g. 'blunder_rate'),
    context dict | None (optional extra info, e.g. {'opening_name': 'Ruy Lopez'} to
    personalize the description).
    Output shape: dict {weakness, training_type, puzzle_themes, training_links,
    description} — a single concrete training recommendation.

    Purpose: map one identified weakness to a concrete, actionable training
    suggestion. Falls back to a generic tactics-puzzle recommendation for any
    metric not in the curated table, rather than returning nothing.
    """
    entry = _WEAKNESS_RECOMMENDATIONS.get(metric)
    if entry is None:
        entry = {
            "training_type": "puzzle",
            "puzzle_themes": ["advantage"],
            "description": f"'{metric}' is a recurring pattern in your games; general tactics "
            "puzzles are a reasonable starting point until a more specific training path is added.",
        }

    puzzle_themes = entry["puzzle_themes"] or []
    training_links = [practice_link(theme) for theme in puzzle_themes]

    description = entry["description"]
    if context and metric == "opening_blunder_rate" and context.get("opening_name"):
        description += f" Your most recently played opening was {context['opening_name']}."

    return {
        "weakness": metric,
        "training_type": entry["training_type"],
        "puzzle_themes": puzzle_themes,
        "training_links": training_links,
        "description": description,
    }


def build_training_plan(
    persistent_weaknesses: list[str],
    vector_df: pd.DataFrame | None = None,
    instances_by_weakness: dict[str, list[dict]] | None = None,
    top_n: int = 5,
) -> list[dict]:
    """Input shape: persistent_weaknesses list[str] (from
    weakness.aggregate.identify_persistent_weaknesses, most severe first --
    NOT the full ranked list; per the 2026-09-22 change request, a training-plan
    card is only built for weaknesses already flagged persistent, one-off
    weaknesses get no card), vector_df optional pd.DataFrame (used only to
    personalize a recommendation, e.g. naming the player's actual opening),
    instances_by_weakness optional dict[str, list[dict]] (from
    nlp.instances.build_instances_by_weakness — concrete per-move examples for
    each weakness), top_n int (cap on how many weaknesses get a card).
    Output shape: list[dict], one recommend_for_weakness() entry per persistent
    weakness, each with an added 'instances' key: a list of {..., the original
    instance fields, 'puzzle_links': list[str]} — one matched puzzle set per
    instance, not just the card's generic category-level links.

    Purpose: the Phase 6 entry point — turns the NLP layer's persistent weakness
    tags (plus their concrete per-move instances) into the final training_plan
    half of Architecture.md §4's Recommendation->Output contract ({text_report,
    training_plan}). Guarantees every weakness the report names gets at least one
    concrete training link (Phases.md Phase 6 done-when criterion), now backed by
    real, personalized examples rather than only a category description.
    """
    context = {}
    if vector_df is not None and not vector_df.empty:
        context["opening_name"] = vector_df.iloc[-1].get("opening_name")
    instances_by_weakness = instances_by_weakness or {}

    plan = []
    for metric in persistent_weaknesses[:top_n]:
        item = recommend_for_weakness(metric, context)
        instances = instances_by_weakness.get(metric, [])
        item["instances"] = [
            {**instance, "practice_links": match_puzzle_for_instance(instance)}
            for instance in instances
        ]
        plan.append(item)
    return plan
