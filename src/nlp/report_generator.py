"""LLM-based natural-language coaching report generation (Phase 5B), upgrading
over the deterministic Phase 5A baseline in templates.py.

Calls the Anthropic Messages API directly via `requests` (already a project
dependency) rather than adding the `anthropic` SDK package, per Rules.md's
constraint on not introducing a new NLP/LLM dependency without checking it
against cost/availability constraints first. Requires ANTHROPIC_API_KEY in the
environment; if it's unset, or the API call fails for any reason, this module
logs a clear warning and falls back to templates.template_report() — the LLM
path is never silently skipped (PRD.md marks it load-bearing for novelty), but
Rules.md §2 also requires that one failed external call never crash the
pipeline, so a report is always produced either way.
"""

import logging
import os

import pandas as pd
import requests

from src.nlp.templates import instance_sentence, metric_label, template_report

logger = logging.getLogger(__name__)

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_API_VERSION = "2023-06-01"
DEFAULT_MODEL = "claude-sonnet-5"
REQUEST_TIMEOUT_SECONDS = 60


def build_report_prompt(
    trend_df: pd.DataFrame,
    persistent: list[str],
    diagnostics: dict[str, dict],
    player_name: str,
    instances_by_weakness: dict[str, list[dict]] | None = None,
) -> str:
    """Input: trend DataFrame, persistent metrics, persistence diagnostics, player name,
    instances. Output: a prompt containing ONLY computed facts, for the LLM path.

    Purpose: keep the LLM grounded -- it may rephrase, but every number, game and move
    it mentions must come from this prompt."""
    lines = [f"Player: {player_name}", f"Games analysed (chronological): {len(trend_df)}", "",
             "Per-metric evidence (rates are per move by this player):"]
    for metric, d in diagnostics.items():
        lines.append(
            f"- {metric_label(metric)}: recent rate {d['ewm']:.2%}, present in {d['presence']:.0%} of games, "
            f"{'PERSISTENT' if d['persistent'] else 'not persistent'}"
        )
    for metric in persistent:
        for inst in (instances_by_weakness or {}).get(metric, []):
            lines.append(f"  example for {metric_label(metric)}: {instance_sentence(inst)}")
    lines += ["", "Write a short, encouraging coaching report (3-5 paragraphs). Use ONLY the facts above. "
              "Do not invent statistics, games, moves or openings. Discuss only weaknesses marked "
              "PERSISTENT as patterns, cite at least one listed example for each by game number and move, "
              "and end with what to practise next."]
    return "\n".join(lines)


def _call_anthropic_api(prompt: str, api_key: str, model: str = DEFAULT_MODEL) -> str:
    """Input shape: prompt str, api_key str, model str.
    Output shape: str, the model's text response.

    Purpose: single wrapped call to the Anthropic Messages API. Raises on any
    failure (network, auth, malformed response) — callers are responsible for
    catching and falling back, per Rules.md §2.
    """
    headers = {
        "x-api-key": api_key,
        "anthropic-version": ANTHROPIC_API_VERSION,
        "content-type": "application/json",
    }
    payload = {
        "model": model,
        "max_tokens": 1024,
        "messages": [{"role": "user", "content": prompt}],
    }
    response = requests.post(
        ANTHROPIC_API_URL, headers=headers, json=payload, timeout=REQUEST_TIMEOUT_SECONDS
    )
    response.raise_for_status()
    data = response.json()
    return "".join(block.get("text", "") for block in data.get("content", []))


def generate_coaching_report(
    trend_df: pd.DataFrame,
    persistent: list[str],
    diagnostics: dict[str, dict],
    player_name: str,
    instances_by_weakness: dict[str, list[dict]] | None = None,
    time_class: str | None = None,
    skipped: int = 0,
    model: str = DEFAULT_MODEL,
) -> dict:
    """Input: as template_report, plus model. Output: {text_report, source: 'llm' | 'template'}.

    Purpose: use the LLM when ANTHROPIC_API_KEY is set, otherwise (or on any failure)
    the deterministic template report -- a report is always produced."""
    fallback = template_report(trend_df, persistent, diagnostics, player_name,
                               instances_by_weakness, time_class, skipped)
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return {"text_report": fallback, "source": "template"}
    prompt = build_report_prompt(trend_df, persistent, diagnostics, player_name, instances_by_weakness)
    try:
        text = _call_anthropic_api(prompt, api_key, model=model)
        if not text.strip():
            raise ValueError("empty response")
        return {"text_report": text, "source": "llm"}
    except Exception as exc:  # noqa: BLE001
        logger.warning("LLM report generation failed (%s); using the template report.", exc)
        return {"text_report": fallback, "source": "template"}
