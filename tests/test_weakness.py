"""Per-game vectors (player's moves only) and the persistence test."""

import pandas as pd

from src.features.motifs import add_motif_column
from src.features.positional import add_positional_columns
from src.weakness.aggregate import (
    TREND_METRICS,
    add_rolling_trends,
    identify_persistent_weaknesses,
    persistence_diagnostics,
)
from src.weakness.vectorize import MIN_PLAYER_MOVES, build_weakness_vector
from tests.helpers import rows_from_moves

SANS = ["e4", "e5", "Nf3", "Nc6", "Bc4", "Bc5", "c3", "Nf6", "d4", "exd4", "cxd4", "Bb4+",
        "Bd2", "Bxd2+", "Nbxd2", "d5", "exd5", "Nxd5", "Qb3", "Nce7", "O-O", "O-O", "Rfe1", "c6"]


def _game(blunder_side):
    """24 plies; one big evaluation drop on the given side's 11th move."""
    evals = [20.0] * (len(SANS) + 1)
    idx = 20 if blunder_side == "white" else 21
    for i in range(idx + 1, len(evals)):
        evals[i] = -500.0 if blunder_side == "white" else 500.0
    best = ["a2a3"] * len(SANS)  # engine "preferred" something else, so the drop counts
    df = rows_from_moves(SANS, evals, player_side="white", best=best)
    return add_motif_column(add_positional_columns(df))


def test_opponent_blunders_do_not_count_against_the_player():
    vec = build_weakness_vector(_game("black"), "g1", {})
    assert vec["blunder_rate"] == 0


def test_player_blunder_rate_is_per_player_move():
    vec = build_weakness_vector(_game("white"), "g1", {})
    assert vec["num_player_moves"] == 12
    assert vec["blunder_rate"] == 1 / 12


def test_short_games_are_excluded():
    short = _game("white").head(2 * (MIN_PLAYER_MOVES - 1))
    assert build_weakness_vector(short, "g1", {}) is None


def _trend(series_by_metric, n=20):
    df = pd.DataFrame({"game_id": [f"g{i}" for i in range(n)], "date": ["2026.01.01"] * n})
    for m in TREND_METRICS:
        df[m] = series_by_metric.get(m, [0.0] * n)
    return add_rolling_trends(df)


def test_recurring_weakness_is_persistent():
    trend = _trend({"blunder_rate": [0.06 if i % 2 else 0.0 for i in range(20)]})
    assert identify_persistent_weaknesses(trend) == ["blunder_rate"]


def test_one_bad_stretch_is_not_persistent():
    # Very high blunder rate, but only in the last 3 games (fails presence + both-halves).
    trend = _trend({"blunder_rate": [0.0] * 17 + [0.3, 0.3, 0.3]})
    diag = persistence_diagnostics(trend)["blunder_rate"]
    assert diag["ewm"] > diag["tau"] and not diag["persistent"]
    assert identify_persistent_weaknesses(trend) == []


def test_needs_enough_games():
    trend = _trend({"blunder_rate": [0.1] * 5}, n=5)
    assert identify_persistent_weaknesses(trend) == []
