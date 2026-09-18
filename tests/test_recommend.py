"""Basic per-module tests for src/recommend/."""

import pandas as pd

from src.recommend.recommender import build_training_plan, recommend_for_weakness


def test_recommend_for_weakness_known_metric():
    rec = recommend_for_weakness("blunder_rate")
    assert rec["training_links"]
    assert all(link.startswith("https://lichess.org/training/") for link in rec["training_links"])


def test_recommend_for_weakness_unknown_metric_has_fallback():
    rec = recommend_for_weakness("some_future_metric")
    assert rec["training_links"]
    assert rec["description"]


def test_recommend_for_weakness_pawn_structure_is_study_note_not_puzzle():
    rec = recommend_for_weakness("pawn_weakness_rate")
    assert rec["training_type"] == "opening_study"
    assert rec["training_links"] == []


def test_build_training_plan_covers_all_ranked_weaknesses():
    ranked = ["blunder_rate", "missed_tactic_rate", "pawn_weakness_rate"]
    vector_df = pd.DataFrame({"opening_name": ["Ruy Lopez"]})
    plan = build_training_plan(ranked, vector_df)
    assert [item["weakness"] for item in plan] == ranked
    for item in plan:
        assert item["training_links"] or item["training_type"] == "opening_study"


def test_build_training_plan_respects_top_n():
    ranked = ["blunder_rate", "mistake_rate", "inaccuracy_rate", "pawn_weakness_rate", "missed_tactic_rate"]
    plan = build_training_plan(ranked, None, top_n=2)
    assert len(plan) == 2
