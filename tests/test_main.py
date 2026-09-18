"""Integration test for src/main.py — the Phase 7 done-when criterion:
one command takes a player's games in and produces a full report + training
plan out, with no manual steps in between.

Uses --pgn-file rather than --username since live Chess.com/Lichess network
access is blocked in this sandbox (see Memory.md); run_pipeline()'s API-pull
path itself is exercised separately (mocked) in tests/test_ingestion.py.
"""

import subprocess
import sys
from pathlib import Path

from src.config import RAW_PGN_DIR
from src.main import run_pipeline

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SMOKE_TEST_DEPTH = 8


def test_run_pipeline_end_to_end_from_pgn_file():
    result = run_pipeline(
        pgn_file=str(RAW_PGN_DIR / "sample_game.pgn"),
        username="TestPlayer",
        depth=SMOKE_TEST_DEPTH,
    )
    assert result["text_report"].strip() != ""
    assert result["games_analyzed"] == 1
    assert isinstance(result["training_plan"], list)
    for item in result["training_plan"]:
        assert item["training_links"] or item["training_type"] == "opening_study"


def test_cli_runs_as_a_single_command(tmp_path):
    """Runs `python -m src.main --pgn-file ... --depth ...` as an actual subprocess,
    the literal "one command" the Phase 7 done-when criterion asks for.
    """
    result = subprocess.run(
        [
            sys.executable, "-m", "src.main",
            "--pgn-file", str(RAW_PGN_DIR / "sample_short_game.pgn"),
            "--depth", str(SMOKE_TEST_DEPTH),
        ],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, f"CLI failed:\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}"
    assert "Training Plan" in result.stdout
    assert "Coaching Report" in result.stdout
