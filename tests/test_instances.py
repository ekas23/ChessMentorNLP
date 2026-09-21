"""Tests for src/nlp/instances.py — the 2026-09-22 change request's per-instance
weakness examples (selection, spread-across-games, capping, narration).
"""

import pandas as pd

from src.nlp.instances import (
    MAX_INSTANCES_PER_WEAKNESS,
    build_instances_by_weakness,
    filter_moves_for_metric,
    select_instances,
)

STARTING_FEN_WHITE = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"


def _row(game_id, move_number, quality_label, motif="", motif_detail="", phase="middlegame", pawn_structure="normal"):
    return {
        "game_id": game_id,
        "move_number": move_number,
        "fen": STARTING_FEN_WHITE,
        "move_uci": "e2e4",
        "eval_before": 0.0,
        "eval_after": -250.0 if quality_label == "blunder" else -60.0,
        "quality_label": quality_label,
        "motif": motif,
        "motif_detail": motif_detail,
        "phase": phase,
        "pawn_structure": pawn_structure,
    }


def _moves_df():
    rows = [
        _row("g1", 5, "blunder"),
        _row("g2", 8, "blunder", motif="fork", motif_detail="a knight fork on f5 attacking the opponent's queen and rook"),
        _row("g3", 12, "mistake"),
        _row("g4", 3, "blunder"),
        _row("g4", 20, "blunder"),  # second blunder in g4 -- should not crowd out other games
        _row("g5", 30, "blunder", phase="endgame"),
    ]
    return pd.DataFrame(rows)


def _game_number_map():
    return {f"g{i}": i for i in range(1, 6)}


def test_filter_moves_for_metric_blunder_rate():
    filtered = filter_moves_for_metric(_moves_df(), "blunder_rate")
    assert set(filtered["game_id"]) == {"g1", "g2", "g4", "g5"}
    assert (filtered["quality_label"] == "blunder").all()


def test_filter_moves_for_metric_missed_tactic_rate():
    filtered = filter_moves_for_metric(_moves_df(), "missed_tactic_rate")
    assert list(filtered["game_id"]) == ["g2"]


def test_filter_moves_for_metric_unknown_returns_empty():
    filtered = filter_moves_for_metric(_moves_df(), "not_a_real_metric")
    assert filtered.empty


def test_select_instances_spreads_across_distinct_games_first():
    instances = select_instances(_moves_df(), "blunder_rate", _game_number_map(), max_instances=3)
    game_ids = [i["game_id"] for i in instances]
    assert len(set(game_ids)) == len(game_ids), "First pass should pick at most one instance per game"


def test_select_instances_prefers_motif_detail_row_first():
    instances = select_instances(_moves_df(), "blunder_rate", _game_number_map(), max_instances=4)
    # g2's blunder has a motif_detail (most explainable) -- should be selected first.
    assert instances[0]["game_id"] == "g2"
    assert "fork" in instances[0]["explanation"]


def test_select_instances_respects_cap():
    instances = select_instances(_moves_df(), "blunder_rate", _game_number_map(), max_instances=2)
    assert len(instances) == 2
    assert MAX_INSTANCES_PER_WEAKNESS == 4  # default stays 4 per the change request


def test_select_instances_empty_for_metric_with_no_candidates():
    empty_df = _moves_df()[_moves_df()["game_id"] == "nonexistent"]
    assert select_instances(empty_df, "blunder_rate", {}) == []


def test_narration_uses_move_san_not_uci():
    instances = select_instances(_moves_df(), "blunder_rate", _game_number_map(), max_instances=1)
    # move_uci 'e2e4' from the starting position should render as SAN 'e4', not 'e2e4'.
    assert "e4" in instances[0]["explanation"]
    assert "e2e4" not in instances[0]["explanation"]


def test_narration_states_centipawn_swing():
    instances = select_instances(_moves_df(), "blunder_rate", _game_number_map(), max_instances=1)
    assert "centipawns" in instances[0]["explanation"]


def test_build_instances_by_weakness_only_covers_persistent_metrics():
    moves_df = _moves_df()
    trend_df = pd.DataFrame({"game_id": ["g1", "g2", "g3", "g4", "g5"]})
    result = build_instances_by_weakness(moves_df, trend_df, ["blunder_rate"])
    assert set(result.keys()) == {"blunder_rate"}  # mistake_rate not requested -> no card
    assert len(result["blunder_rate"]) <= MAX_INSTANCES_PER_WEAKNESS


def test_build_instances_by_weakness_empty_persistent_list_returns_empty_dict():
    moves_df = _moves_df()
    trend_df = pd.DataFrame({"game_id": ["g1", "g2", "g3", "g4", "g5"]})
    assert build_instances_by_weakness(moves_df, trend_df, []) == {}
