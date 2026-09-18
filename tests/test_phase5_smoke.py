"""Phase 5 smoke test: move-to-text templating + LLM-based coaching report generation.

Done-when criteria (Phases.md, Phase 5): running the pipeline on a real player
produces a coherent multi-paragraph coaching report, not just printed stats.

ANTHROPIC_API_KEY is not set in this sandboxed session, so generate_coaching_report()
is expected to exercise its documented fallback path (source == 'template_fallback')
here. The LLM path (source == 'llm') is fully implemented and will be used
automatically wherever ANTHROPIC_API_KEY is present — see Memory.md.
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.nlp.report_generator import build_report_prompt, generate_coaching_report  # noqa: E402
from src.nlp.templates import move_to_text, template_report  # noqa: E402
from src.weakness.aggregate import add_rolling_trends, identify_persistent_weaknesses, rank_weakness_tags, sort_chronologically  # noqa: E402


def _build_synthetic_timeline() -> pd.DataFrame:
    """Reuses the same synthetic 8-game timeline shape as the Phase 4 smoke test
    (sustained blunder-rate rise) so this phase has a realistic persistent
    weakness to actually narrate."""
    dates = [f"2026.0{i}.01" for i in range(1, 9)]
    blunder_rates = [0.05, 0.05, 0.08, 0.20, 0.22, 0.25, 0.23, 0.24]
    vector_df = pd.DataFrame(
        {
            "game_id": [f"game_{i}" for i in range(8)],
            "date": dates,
            "num_moves": [30] * 8,
            "blunder_rate": blunder_rates,
            "mistake_rate": [0.05] * 8,
            "inaccuracy_rate": [0.05] * 8,
            "pawn_weakness_rate": [0.12] * 8,
            "king_safety_avg": [2.0] * 8,
            "missed_tactic_rate": [0.02] * 8,
            "opening_name": ["Ruy Lopez"] * 8,
        }
    )
    return add_rolling_trends(sort_chronologically(vector_df))


def test_move_to_text() -> None:
    row = {"move_number": 3, "move_uci": "d1h5", "quality_label": "mistake", "phase": "opening", "motif": "pin"}
    text = move_to_text(row)
    print(f"move_to_text: {text}")
    assert "move 3" in text and "mistake" in text and "pin" in text


def test_template_report_is_coherent_and_multi_paragraph() -> None:
    trend_df = _build_synthetic_timeline()
    persistent = identify_persistent_weaknesses(trend_df)
    ranked = rank_weakness_tags(trend_df, persistent)
    report = template_report(trend_df, ranked, "Test Player")
    print("\n--- Template (Phase 5A baseline) report ---")
    print(report)

    paragraphs = [p for p in report.split("\n\n") if p.strip()]
    assert len(paragraphs) >= 3, f"Expected a multi-paragraph report, got {len(paragraphs)} paragraph(s)"
    assert "blunder" in report.lower()
    assert "Test Player" in report


def test_generate_coaching_report_falls_back_without_api_key() -> None:
    trend_df = _build_synthetic_timeline()
    ranked = rank_weakness_tags(trend_df)

    prompt = build_report_prompt(trend_df, ranked, "Test Player")
    print("\n--- LLM prompt that would be sent (for inspection) ---")
    print(prompt)
    assert "Test Player" in prompt
    assert "blunder_rate" in prompt

    result = generate_coaching_report(trend_df, ranked, "Test Player")
    print(f"\ngenerate_coaching_report source: {result['source']}")
    assert result["source"] == "template_fallback", (
        "Expected fallback since ANTHROPIC_API_KEY is not set in this environment"
    )
    paragraphs = [p for p in result["text_report"].split("\n\n") if p.strip()]
    assert len(paragraphs) >= 3
    assert result["text_report"].strip() != ""


def main() -> None:
    test_move_to_text()
    test_template_report_is_coherent_and_multi_paragraph()
    test_generate_coaching_report_falls_back_without_api_key()
    print("\nPhase 5 smoke test PASSED: move-to-text templating works, and "
          "generate_coaching_report() produces a coherent multi-paragraph report "
          "(via its documented fallback path, since no ANTHROPIC_API_KEY is set here).")


if __name__ == "__main__":
    main()
