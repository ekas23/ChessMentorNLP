"""Basic per-module tests for src/nlp/."""

import pandas as pd

from src.nlp.report_generator import build_report_prompt, generate_coaching_report
from src.nlp.templates import move_to_text, template_report, weakness_summary_sentence


def _trend_df():
    return pd.DataFrame(
        {
            "game_id": ["g1", "g2"],
            "blunder_rate": [0.1, 0.3],
            "blunder_rate_ewm": [0.15, 0.28],
            "opening_name": ["Ruy Lopez", "Ruy Lopez"],
        }
    )


def test_move_to_text_includes_key_facts():
    text = move_to_text({"move_number": 5, "move_uci": "e2e4", "quality_label": "blunder", "phase": "opening", "motif": ""})
    assert "move 5" in text
    assert "blunder" in text


def test_move_to_text_good_move_wording():
    text = move_to_text({"move_number": 1, "move_uci": "e2e4", "quality_label": "good", "phase": "opening", "motif": ""})
    assert "solid move" in text


def test_weakness_summary_sentence_formats_percent():
    sentence = weakness_summary_sentence("blunder_rate", 0.21)
    assert "21%" in sentence


def test_template_report_is_multi_paragraph_and_grounded():
    report = template_report(_trend_df(), ["blunder_rate"], "Alice")
    assert "Alice" in report
    assert len([p for p in report.split("\n\n") if p.strip()]) >= 3


def test_template_report_handles_no_weaknesses():
    report = template_report(_trend_df(), [], "Alice")
    assert "No clear recurring weakness" in report


def test_build_report_prompt_grounds_in_real_data_only():
    prompt = build_report_prompt(_trend_df(), ["blunder_rate"], "Alice")
    assert "Alice" in prompt
    assert "blunder_rate" in prompt
    assert "do not invent" in prompt.lower()


def test_generate_coaching_report_falls_back_without_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    result = generate_coaching_report(_trend_df(), ["blunder_rate"], "Alice")
    assert result["source"] == "template_fallback"
    assert result["text_report"].strip() != ""
