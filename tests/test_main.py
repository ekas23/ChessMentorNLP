"""Integration tests for src/main.py — the Phase 7 done-when criterion:
one command takes a Chess.com username + game count in and produces a full
report + training plan out, with no manual steps in between.

Single-input model (2026-09-21 scope change, see Memory.md): run_pipeline()
is now username + max_games only -- no pgn_file parameter. The live
Chess.com path is exercised here via mocked HTTP responses (real network is
blocked in this sandbox); the underlying pipeline-processing logic is
exercised directly via main._run_pipeline_on_games() against real local PGN
fixtures, so the whole annotate->feature->weakness->nlp->recommend chain is
still verified against real Stockfish output without needing live network.
"""

import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.config import RAW_PGN_DIR
from src.ingestion.fetch_games import ChessComUsernameNotFoundError
from src.ingestion.parse_pgn import parse_pgn_file
from src.main import _run_pipeline_on_games, run_pipeline

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SMOKE_TEST_DEPTH = 8


def test_pipeline_core_end_to_end_on_real_games():
    """Exercises the real annotate->feature->weakness->nlp->recommend chain
    against a real local PGN fixture, bypassing the live Chess.com fetch.
    """
    games = parse_pgn_file(str(RAW_PGN_DIR / "sample_game.pgn"))
    result = _run_pipeline_on_games(games, player_name="TestPlayer", depth=SMOKE_TEST_DEPTH)

    assert result["text_report"].strip() != ""
    assert result["games_analyzed"] == 1
    assert isinstance(result["training_plan"], list)
    for item in result["training_plan"]:
        assert item["training_links"] or item["training_type"] == "opening_study"


def test_run_pipeline_fetches_from_chess_com_and_reports_coverage(tmp_path):
    """Mocks the Chess.com API (archives + one month) to return a real PGN fixture's
    content, confirming run_pipeline()'s live path wires fetch_last_n_games straight
    into the rest of the pipeline, and that requesting more games than exist is
    reported clearly rather than erroring.
    """
    pgn_text = Path(RAW_PGN_DIR / "sample_short_game.pgn").read_text()

    archives_resp = MagicMock()
    archives_resp.status_code = 200
    archives_resp.ok = True
    archives_resp.json.return_value = {"archives": ["https://api.chess.com/pub/player/u/games/2026/01"]}

    month_resp = MagicMock()
    month_resp.status_code = 200
    month_resp.ok = True
    month_resp.json.return_value = {"games": [{"pgn": pgn_text}]}

    with patch("src.ingestion.fetch_games.requests.get", side_effect=[archives_resp, month_resp]):
        result = run_pipeline(username="TestPlayer", max_games=50, depth=SMOKE_TEST_DEPTH)

    assert result["games_analyzed"] == 1
    assert result["games_requested"] == 50
    assert result["games_analyzed"] < result["games_requested"]


def test_run_pipeline_raises_clear_error_for_unknown_username():
    not_found_resp = MagicMock()
    not_found_resp.status_code = 404
    with patch("src.ingestion.fetch_games.requests.get", return_value=not_found_resp):
        try:
            run_pipeline(username="definitely_not_a_real_user", max_games=10)
            assert False, "Expected ChessComUsernameNotFoundError"
        except ChessComUsernameNotFoundError:
            pass


def test_cli_shows_usage_without_username():
    """The CLI's single required input is --username; running without it should
    fail fast with a usage error (argparse), not attempt a pipeline run.
    """
    result = subprocess.run(
        [sys.executable, "-m", "src.main"],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode != 0
    assert "--username" in result.stderr or "required" in result.stderr.lower()
