"""Phase 6 smoke test: weakness tag -> training recommendation mapping.

Done-when criteria (Phases.md, Phase 6): each identified weakness in the report
links to at least one concrete training suggestion.
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.recommend.recommender import build_training_plan, recommend_for_weakness  # noqa: E402
from src.weakness.aggregate import add_rolling_trends, identify_persistent_weaknesses, rank_weakness_tags, sort_chronologically  # noqa: E402


def _build_synthetic_timeline() -> pd.DataFrame:
    dates = [f"2026.0{i}.01" for i in range(1, 9)]
    blunder_rates = [0.05, 0.05, 0.08, 0.20, 0.22, 0.25, 0.23, 0.24]
    vector_df = pd.DataFrame(
        {
            "game_id": [f"game_{i}" for i in range(8)],
            "date": dates,
            "blunder_rate": blunder_rates,
            "mistake_rate": [0.05] * 8,
            "inaccuracy_rate": [0.05] * 8,
            "pawn_weakness_rate": [0.12] * 8,
            "missed_tactic_rate": [0.02] * 8,
            "opening_name": ["Ruy Lopez"] * 8,
        }
    )
    return add_rolling_trends(sort_chronologically(vector_df))


def test_single_weakness_recommendation() -> None:
    rec = recommend_for_weakness("missed_tactic_rate")
    print(f"missed_tactic_rate -> {rec}")
    assert rec["training_links"], "Expected at least one training link"
    assert set(rec["puzzle_themes"]) == {"fork", "pin", "skewer"}
    for link in rec["training_links"]:
        assert link.startswith("https://lichess.org/training/")


def test_training_plan_covers_every_identified_weakness() -> None:
    trend_df = _build_synthetic_timeline()
    persistent = identify_persistent_weaknesses(trend_df)
    ranked = rank_weakness_tags(trend_df, persistent)
    print(f"Ranked weakness tags: {ranked}")

    plan = build_training_plan(ranked, trend_df)
    print("\nTraining plan:")
    for item in plan:
        print(f"- {item['weakness']}: {item['training_type']} -> {item['training_links']} :: {item['description']}")

    assert len(plan) == len(ranked[:5]), "Expected one recommendation per (top-5) ranked weakness"
    for item, metric in zip(plan, ranked[:5]):
        assert item["weakness"] == metric
        assert item["training_links"] or item["training_type"] == "opening_study", (
            f"'{metric}' has no concrete training suggestion"
        )
        assert item["description"].strip() != ""

    # The dominant weakness in this synthetic data is blunder_rate -- confirm it's covered.
    blunder_item = next(item for item in plan if item["weakness"] == "blunder_rate")
    assert blunder_item["training_links"], "blunder_rate must have a concrete link"


def main() -> None:
    test_single_weakness_recommendation()
    test_training_plan_covers_every_identified_weakness()
    print("\nPhase 6 smoke test PASSED: every identified weakness maps to at least one "
          "concrete training suggestion.")


if __name__ == "__main__":
    main()
