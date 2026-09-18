"""Phase 4 smoke test: weakness vectorization + longitudinal trend aggregation.

Done-when criteria (Phases.md, Phase 4): given a chronological batch of games,
you get a timeline showing at least one clearly identifiable persistent
weakness pattern.
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.annotation.engine import annotate_games, derive_game_id  # noqa: E402
from src.config import RAW_PGN_DIR  # noqa: E402
from src.features.motifs import add_motif_column  # noqa: E402
from src.features.openings import add_opening_columns  # noqa: E402
from src.features.positional import add_positional_columns  # noqa: E402
from src.ingestion.parse_pgn import parse_pgn_file  # noqa: E402
from src.weakness.aggregate import add_rolling_trends, identify_persistent_weaknesses, sort_chronologically  # noqa: E402
from src.weakness.vectorize import vectorize_games  # noqa: E402

SMOKE_TEST_DEPTH = 8


def test_real_pipeline_produces_valid_weakness_vector() -> None:
    """Runs the real annotate->feature->vectorize chain end to end on one real game,
    confirming the weakness vector has the right shape and sane values.
    """
    games = parse_pgn_file(str(RAW_PGN_DIR / "sample_short_game.pgn"))
    game_ids = [derive_game_id(games[0], 0)]

    df = annotate_games(games, depth=SMOKE_TEST_DEPTH)
    df = add_positional_columns(df)
    df = add_motif_column(df)
    df = add_opening_columns(df, games, game_ids)

    vector_df = vectorize_games(df, games, game_ids)
    print(vector_df.to_string(index=False))

    assert len(vector_df) == 1
    row = vector_df.iloc[0]
    assert row["num_moves"] == len(list(games[0].mainline_moves()))
    assert 0.0 <= row["blunder_rate"] <= 1.0
    assert 0.0 <= row["mistake_rate"] <= 1.0
    assert 0.0 <= row["missed_tactic_rate"] <= 1.0
    print("Real pipeline: weakness vector shape and value ranges are valid\n")


def test_persistent_weakness_is_identified_in_a_timeline() -> None:
    """Constructs a synthetic 8-game chronological weakness-vector timeline with a
    deliberate, sustained rise in blunder_rate (simulating a player who develops a
    persistent tactical weakness) alongside a metric that only spikes once (a
    transient blip that should NOT be flagged as persistent) — this directly checks
    the "transient vs. persistent" distinction that is this project's core claim.
    """
    dates = [f"2026.0{i}.01" for i in range(1, 9)]
    # Sustained rise: player's blunder rate climbs and stays high for the last 4 games.
    blunder_rates = [0.05, 0.05, 0.08, 0.20, 0.22, 0.25, 0.23, 0.24]
    # Transient blip: one bad game, then back to normal — must NOT be flagged persistent.
    mistake_rates = [0.05, 0.05, 0.05, 0.40, 0.05, 0.05, 0.05, 0.05]

    vector_df = pd.DataFrame(
        {
            "game_id": [f"game_{i}" for i in range(8)],
            "date": dates,
            "num_moves": [30] * 8,
            "blunder_rate": blunder_rates,
            "mistake_rate": mistake_rates,
            "inaccuracy_rate": [0.05] * 8,
            "pawn_weakness_rate": [0.1] * 8,
            "king_safety_avg": [2.0] * 8,
            "missed_tactic_rate": [0.0] * 8,
        }
    )

    sorted_df = sort_chronologically(vector_df)
    trend_df = add_rolling_trends(sorted_df)
    print(trend_df[["game_id", "date", "blunder_rate", "blunder_rate_ewm",
                     "mistake_rate", "mistake_rate_ewm"]].to_string(index=False))

    persistent = identify_persistent_weaknesses(trend_df)
    print(f"\nIdentified persistent weaknesses: {persistent}")

    assert "blunder_rate" in persistent, "Expected the sustained blunder-rate rise to be flagged persistent"
    assert "mistake_rate" not in persistent, "A one-off spike should NOT be flagged as a persistent weakness"


def main() -> None:
    test_real_pipeline_produces_valid_weakness_vector()
    test_persistent_weakness_is_identified_in_a_timeline()
    print("\nPhase 4 smoke test PASSED: weakness vectors build correctly from real data, "
          "and the longitudinal timeline correctly distinguishes a persistent weakness "
          "from a transient one-off.")


if __name__ == "__main__":
    main()
