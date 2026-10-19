"""Instance selection, narration, report text and training-plan links."""

import pandas as pd

from src.features.motifs import add_motif_column
from src.features.positional import add_positional_columns
from src.nlp.instances import filter_moves_for_metric, select_instances
from src.nlp.templates import baseline_report, instance_sentence, metric_label, rate_phrase, template_report
from src.recommend.recommender import build_training_plan, match_puzzle_for_instance
from src.weakness.aggregate import add_rolling_trends, persistence_diagnostics
from tests.helpers import rows_from_moves


def _hanging_knight_game():
    # 1. e4 e5 2. Nf3 Nc6 3. Ng5? (engine said Bc4) Qxg5 -- the knight is lost.
    sans = ["e4", "e5", "Nf3", "Nc6", "Ng5", "Qxg5"]
    evals = [20, 20, 20, 20, 20, -350, -350]
    best = ["e2e4", "e7e5", "g1f3", "b8c6", "f1c4", "d8g5"]
    df = rows_from_moves(sans, evals, player_side="white", best=best)
    df.loc[df["move_san"] == "Ng5", "best_reply_uci"] = "d8g5"
    return add_motif_column(add_positional_columns(df))


def test_blunder_card_only_draws_blunders_by_the_player():
    df = _hanging_knight_game()
    rows = filter_moves_for_metric(df, "blunder_rate")
    assert list(rows["move_san"]) == ["Ng5"]


def test_instance_names_full_move_number_and_hanging_piece():
    df = _hanging_knight_game()
    info = {"g1": {"number": 7, "date": "2026.09.01", "opponent": "Bob", "link": "https://example/game/1"}}
    [inst] = select_instances(df, "blunder_rate", info)
    assert inst["move_label"] == "3. Ng5"
    assert "left your knight on g5 to be taken by Qxg5" in inst["explanation"]
    assert "The engine preferred Bc4." in inst["explanation"]
    assert inst["position_url"].startswith("https://lichess.org/analysis/standard/")
    sentence = instance_sentence(inst)
    assert sentence.startswith("In game 7 (vs Bob, 2026.09.01), on 3. Ng5: It left")
    assert [link["label"] for link in match_puzzle_for_instance(inst)] == ["Lichess hanging-piece puzzles"]


def test_rate_phrase_and_labels_are_readable():
    assert rate_phrase(0.02) == "2.0% of your moves (about one in every 50)"
    assert metric_label("missed_tactic_rate") == "Missed tactics"


def _trend():
    n = 12
    df = pd.DataFrame({"game_id": [f"g{i}" for i in range(n)], "date": ["2026.01.01"] * n,
                       "blunder_rate": [0.05 if i % 2 else 0.0 for i in range(n)],
                       "mistake_rate": [0.0] * (n - 1) + [0.2], "inaccuracy_rate": [0.0] * n,
                       "missed_tactic_rate": [0.0] * n, "pawn_weakness_rate": [0.0] * n})
    return add_rolling_trends(df)


def test_template_report_explains_flagged_and_unflagged():
    trend = _trend()
    diag = persistence_diagnostics(trend)
    text = template_report(trend, ["blunder_rate"], diag, "alice", {}, "rapid", skipped=2)
    assert "last 12 rapid games" in text
    assert "2 very short games were left out" in text
    assert "- Blunders: recently" in text
    assert "Also tracked but not flagged: mistakes." in text


def test_baseline_report_has_no_examples_or_persistence():
    text = baseline_report(_trend(), "alice")
    assert "Blunders" in text and "In game" not in text and "recurring" not in text


def test_training_plan_cards_carry_labelled_links():
    plan = build_training_plan(["missed_tactic_rate"], _trend(),
                               {"missed_tactic_rate": [{"metric": "missed_tactic_rate", "motif": "pin",
                                                         "quality_label": "mistake", "explanation": ""}]})
    card = plan[0]
    assert card["training_links"][0]["url"].startswith("https://lichess.org/training/")
    assert card["instances"][0]["practice_links"] == [
        {"url": "https://lichess.org/training/pin", "label": "Lichess pin puzzles"}]
