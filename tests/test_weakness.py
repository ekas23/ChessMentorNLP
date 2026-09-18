"""Basic per-module tests for src/weakness/."""

import pandas as pd
import pytest

from src.weakness.aggregate import (
    add_rolling_trends,
    identify_persistent_weaknesses,
    rank_weakness_tags,
    sort_chronologically,
)
from src.weakness.vectorize import build_weakness_vector, vectorize_games


def _sample_moves_df():
    return pd.DataFrame(
        {
            "game_id": ["g1"] * 4,
            "move_number": [1, 2, 3, 4],
            "quality_label": ["good", "blunder", "good", "mistake"],
            "phase": ["opening", "opening", "middlegame", "middlegame"],
            "pawn_structure": ["normal", "isolated", "normal", "normal"],
            "king_safety": [3, 2, 2, 1],
            "motif": ["", "fork", "", ""],
            "eco": ["C60-C99"] * 4,
            "opening_name": ["Ruy Lopez"] * 4,
        }
    )


def test_build_weakness_vector_rates():
    vec = build_weakness_vector(_sample_moves_df(), "g1", "2026.01.01")
    assert vec["num_moves"] == 4
    assert vec["blunder_rate"] == 0.25
    assert vec["mistake_rate"] == 0.25
    assert vec["pawn_weakness_rate"] == 0.25
    assert vec["opening_name"] == "Ruy Lopez"


def test_build_weakness_vector_raises_on_empty():
    with pytest.raises(ValueError):
        build_weakness_vector(pd.DataFrame(), "g1", None)


def test_vectorize_games_skips_games_with_no_rows():
    class FakeGame:
        headers = {"Date": "2026.01.01"}

    games = [FakeGame(), FakeGame()]
    df = vectorize_games(_sample_moves_df(), games, ["g1", "missing_game"])
    assert len(df) == 1
    assert df.iloc[0]["game_id"] == "g1"


def _synthetic_timeline():
    dates = [f"2026.0{i}.01" for i in range(1, 9)]
    blunder_rates = [0.05, 0.05, 0.08, 0.20, 0.22, 0.25, 0.23, 0.24]
    mistake_rates = [0.05, 0.05, 0.05, 0.40, 0.05, 0.05, 0.05, 0.05]
    return pd.DataFrame(
        {
            "game_id": [f"game_{i}" for i in range(8)],
            "date": dates,
            "blunder_rate": blunder_rates,
            "mistake_rate": mistake_rates,
            "inaccuracy_rate": [0.05] * 8,
            "pawn_weakness_rate": [0.1] * 8,
            "missed_tactic_rate": [0.0] * 8,
        }
    )


def test_sort_chronologically_orders_by_date():
    df = _synthetic_timeline().iloc[::-1].reset_index(drop=True)  # shuffle into reverse order
    sorted_df = sort_chronologically(df)
    assert list(sorted_df["date"]) == sorted(sorted_df["date"].tolist())


def test_identify_persistent_weaknesses_flags_sustained_rise():
    trend_df = add_rolling_trends(sort_chronologically(_synthetic_timeline()))
    persistent = identify_persistent_weaknesses(trend_df)
    assert "blunder_rate" in persistent
    assert "mistake_rate" not in persistent  # one-off spike, not sustained


def test_identify_persistent_weaknesses_empty_with_too_few_games():
    small_df = add_rolling_trends(sort_chronologically(_synthetic_timeline().head(2)))
    assert identify_persistent_weaknesses(small_df) == []


def test_rank_weakness_tags_orders_by_severity():
    trend_df = add_rolling_trends(sort_chronologically(_synthetic_timeline()))
    ranked = rank_weakness_tags(trend_df)
    assert ranked[0] == "blunder_rate"
