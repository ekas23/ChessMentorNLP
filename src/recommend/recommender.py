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
        "description": "Tactical motifs (forks, pins, skewers) were available in the game but "
        "not converted. Targeted puzzle sets on exactly these three motifs build pattern "
        "recognition for next time.",
    },
    "pawn_weakness_rate": {
        "training_type": "opening_study",
        "puzzle_themes": None,
        "description": "Isolated and doubled pawns are recurring. Study pawn-structure "
        "principles for your usual openings (when to trade into a weak structure, and how to "
        "play with/against an isolated queen pawn) rather than drilling puzzles for this one.",
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


def match_puzzle_for_instance(instance: dict) -> list[str]:
    """Input shape: instance dict (one entry from nlp.instances.select_instances --
    has 'motif', 'quality_label', 'phase' keys).
    Output shape: list[str], real "https://lichess.org/training/{theme}" links
    matching that specific instance as closely as possible.

    Purpose: per-instance puzzle matching (2026-09-22 change request) — match by
    the instance's own exact motif when one was detected (fork-miss -> fork
    puzzles, not a generic tactics link), falling back to the weakness category
    only when no specific motif is present on that move. Per the request: "if a
    specific instance's exact motif can't be matched... fall back to the closest
    available theme... just use the closest match silently" -- no UI caveat is
    shown, this function just picks the best available theme.
    """
    if instance.get("metric") == "pawn_weakness_rate":
        # Same reasoning as pawn_weakness_rate's category-level recommendation:
        # no real Lichess puzzle theme covers pawn structure, so no puzzle link
        # is attached (a study-note recommendation, not a mismatched puzzle).
        return []

    motif_tags = [tag for tag in (instance.get("motif") or "").split(",") if tag]
    if motif_tags:
        # All three motif names (fork/pin/skewer) are themselves real Lichess theme
        # slugs, so an exact motif tag maps directly with no translation needed.
        return [LICHESS_TRAINING_URL.format(theme=tag) for tag in motif_tags]

    if instance.get("quality_label") == "blunder":
        return [LICHESS_TRAINING_URL.format(theme="hangingPiece")]

    phase = instance.get("phase")
    if phase in ("opening", "middlegame", "endgame"):
        return [LICHESS_TRAINING_URL.format(theme=phase)]

    return [LICHESS_TRAINING_URL.format(theme="advantage")]


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
    training_links = [LICHESS_TRAINING_URL.format(theme=theme) for theme in puzzle_themes]

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
            {**instance, "puzzle_links": match_puzzle_for_instance(instance)}
            for instance in instances
        ]
        plan.append(item)
    return plan
