"""Basic per-module tests for src/recommend/."""

import pandas as pd

from src.recommend.recommender import build_training_plan, match_puzzle_for_instance, recommend_for_weakness


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


def test_match_puzzle_for_instance_exact_motif():
    links = match_puzzle_for_instance({"motif": "fork", "quality_label": "blunder", "phase": "middlegame"})
    assert links == ["https://lichess.org/training/fork"]


def test_match_puzzle_for_instance_multiple_motifs():
    links = match_puzzle_for_instance({"motif": "fork,pin", "quality_label": "blunder"})
    assert "https://lichess.org/training/fork" in links
    assert "https://lichess.org/training/pin" in links


def test_match_puzzle_for_instance_falls_back_to_blunder_theme():
    links = match_puzzle_for_instance({"motif": "", "quality_label": "blunder", "phase": "middlegame"})
    assert links == ["https://lichess.org/training/hangingPiece"]


def test_match_puzzle_for_instance_falls_back_to_phase_theme():
    links = match_puzzle_for_instance({"motif": "", "quality_label": "mistake", "phase": "endgame"})
    assert links == ["https://lichess.org/training/endgame"]


def test_match_puzzle_for_instance_pawn_weakness_has_no_puzzle():
    links = match_puzzle_for_instance({"metric": "pawn_weakness_rate", "motif": "", "quality_label": "good"})
    assert links == []


def test_build_training_plan_attaches_instances_with_per_instance_puzzle_links():
    persistent = ["blunder_rate"]
    instances_by_weakness = {
        "blunder_rate": [
            {"game_id": "g1", "game_number": 1, "move_number": 12, "quality_label": "blunder",
             "motif": "fork", "phase": "middlegame", "metric": "blunder_rate", "explanation": "..."},
        ]
    }
    plan = build_training_plan(persistent, None, instances_by_weakness)
    assert len(plan) == 1
    assert plan[0]["instances"][0]["puzzle_links"] == ["https://lichess.org/training/fork"]


def test_build_training_plan_no_instances_key_is_empty_list_not_missing():
    plan = build_training_plan(["blunder_rate"], None, instances_by_weakness=None)
    assert plan[0]["instances"] == []
