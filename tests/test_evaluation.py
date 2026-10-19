"""Evaluation helpers and the cohort -> annotation-sheet -> scoring workflow (offline)."""

import subprocess
import sys
from unittest.mock import patch

import pandas as pd
import pytest

from src.config import RAW_PGN_DIR
from src.evaluation.metrics import cohen_kappa, split_half_agreement
from src.ingestion.parse_pgn import parse_pgn_file
from tests.helpers import requires_stockfish


def test_cohen_kappa_known_values():
    assert cohen_kappa([1, 0, 1, 0], [1, 0, 1, 0]) == pytest.approx(1.0)
    assert cohen_kappa([1, 1, 0, 0], [1, 0, 1, 0]) == pytest.approx(0.0)
    assert cohen_kappa([1, 1, 1, 0, 0, 0], [1, 1, 0, 0, 0, 1]) == pytest.approx(1 / 3)


def test_split_half_agrees_on_a_stable_player():
    n = 30
    df = pd.DataFrame({"game_id": range(n), "date": ["2026.01.01"] * n,
                       "blunder_rate": [0.08 if i % 2 else 0.0 for i in range(n)],
                       "mistake_rate": [0.0] * n, "inaccuracy_rate": [0.0] * n,
                       "missed_tactic_rate": [0.0] * n, "pawn_weakness_rate": [0.0] * n})
    res = split_half_agreement(df)
    assert res["first"] == res["second"] == ["blunder_rate"]
    assert res["agreement"] == 1.0 and res["jaccard"] == 1.0


@requires_stockfish
def test_cohort_to_annotation_sheet_to_scores(tmp_path):
    from scripts import export_motif_sample, run_cohort

    accounts = tmp_path / "accounts.csv"
    accounts.write_text("username,band\nTestPlayer,800-1200\n")
    games = parse_pgn_file(str(RAW_PGN_DIR / "synthetic_games.pgn"))
    out = tmp_path / "cohort"
    with patch.object(run_cohort, "fetch_last_n_games", return_value=games), \
         patch.object(sys, "argv", ["run_cohort", "--accounts", str(accounts), "--depth", "12", "--out", str(out)]):
        run_cohort.main()
    summary = pd.read_csv(out / "cohort_summary.csv")
    assert summary.loc[0, "games"] == 24
    assert (out / "TestPlayer" / "moves.csv").is_file()

    # Make sure there is at least one missed tactic to sample, then export.
    moves = pd.read_csv(out / "TestPlayer" / "moves.csv")
    if not (moves["missed_tactic"] & moves["is_player"]).any():
        first_player_row = moves.index[moves["is_player"]][0]
        moves.loc[first_player_row, ["missed_tactic", "motif", "motif_detail"]] = [True, "fork", "x"]
        moves.to_csv(out / "TestPlayer" / "moves.csv", index=False)
    sheet_path = tmp_path / "sheet.csv"
    with patch.object(sys, "argv", ["export", "--cohort", str(out), "--out", str(sheet_path)]):
        export_motif_sample.main()
    sheet = pd.read_csv(sheet_path)
    assert {"position_link", "claim", "annotator_A", "annotator_B"} <= set(sheet.columns)

    sheet["annotator_A"], sheet["annotator_B"] = 1, 1
    sheet.to_csv(sheet_path, index=False)
    proc = subprocess.run([sys.executable, "-m", "scripts.score_motif_annotations", str(sheet_path)],
                          capture_output=True, text=True, check=True)
    assert "precision (both agree):  1.000" in proc.stdout
