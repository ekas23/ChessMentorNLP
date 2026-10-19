"""End-to-end pipeline on local PGN fixtures (no network)."""

from unittest.mock import patch

import pytest

from src.config import RAW_PGN_DIR
from src.ingestion.parse_pgn import parse_pgn_file
from src.main import analyse_games, run_pipeline
from tests.helpers import requires_stockfish

SYNTHETIC = RAW_PGN_DIR / "synthetic_games.pgn"


@requires_stockfish
def test_pipeline_end_to_end_on_synthetic_games():
    games = parse_pgn_file(str(SYNTHETIC))[:12]
    result = analyse_games(games, username="TestPlayer", depth=10, return_moves=True)
    assert result["games_analyzed"] + result["games_skipped"] == 12
    moves = result["moves"]
    assert set(moves["is_player"]) == {True, False}
    # The deliberately weak side should err more often than its stronger opponent.
    mine = moves[moves["is_player"]]["quality_label"].isin(["blunder", "mistake"]).mean()
    theirs = moves[~moves["is_player"]]["quality_label"].isin(["blunder", "mistake"]).mean()
    assert mine > theirs
    for row in result["timeline"]:
        assert 0 <= row["blunder_rate"] < 0.5
    for card in result["training_plan"]:
        for inst in card["instances"]:
            assert inst["metric"] == card["weakness"]
    assert result["text_report"].startswith("Coaching report for TestPlayer")


def test_run_pipeline_passes_time_class_to_ingestion():
    with patch("src.main.fetch_last_n_games", return_value=[]) as fetch:
        with pytest.raises(RuntimeError):
            run_pipeline("alice", max_games=5, time_class="rapid")
    fetch.assert_called_once_with("alice", n=5, time_class="rapid")
