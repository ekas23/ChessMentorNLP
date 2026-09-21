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

from src.nlp.templates import template_report

logger = logging.getLogger(__name__)

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_API_VERSION = "2023-06-01"
DEFAULT_MODEL = "claude-sonnet-5"
REQUEST_TIMEOUT_SECONDS = 60


def build_report_prompt(
    vector_df: pd.DataFrame,
    ranked_weakness_tags: list[str],
    player_name: str,
    instances_by_weakness: dict[str, list[dict]] | None = None,
) -> str:
    """Input shape: vector_df (trend-augmented weakness-vector DataFrame, chronologically
    sorted), ranked_weakness_tags list[str], player_name str, instances_by_weakness
    optional dict[str, list[dict]] (from nlp.instances.build_instances_by_weakness --
    concrete per-move examples for each *persistent* weakness only; 2026-09-22 change
    request, "Personalized Training Plan with Game Examples").
    Output shape: str, a structured prompt summarizing the player's computed stats
    and concrete example moments.

    Purpose: ground the LLM strictly in the pipeline's own computed numbers AND its
    own selected, real per-move instances (never letting the model invent a game
    number, move, or motif) — required for this to remain a "grounded NLP
    framework" per PRD.md, and to satisfy Rules.md's "never fabricate domain facts."
    Passing the instance data lets the generated narrative reference the player's
    own games concretely ("In Game 12, move 18...") instead of speaking only in
    aggregate rates, which is this change request's central ask for Phase 5.
    """
    games_analyzed = len(vector_df)
    latest = vector_df.iloc[-1] if not vector_df.empty else None

    lines = [
        f"Player: {player_name}",
        f"Games analyzed (chronological): {games_analyzed}",
        "",
        "Ranked recurring weaknesses (most severe/persistent first):",
    ]
    for rank, metric in enumerate(ranked_weakness_tags[:5], start=1):
        ewm_col = f"{metric}_ewm"
        if latest is not None and ewm_col in vector_df.columns:
            lines.append(f"{rank}. {metric}: current trend rate = {latest[ewm_col]:.2%}")
        else:
            lines.append(f"{rank}. {metric}")

    if latest is not None:
        lines += [
            "",
            "Most recent game summary:",
            f"- blunder_rate: {latest.get('blunder_rate', 0):.2%}",
            f"- mistake_rate: {latest.get('mistake_rate', 0):.2%}",
            f"- inaccuracy_rate: {latest.get('inaccuracy_rate', 0):.2%}",
            f"- pawn_weakness_rate: {latest.get('pawn_weakness_rate', 0):.2%}",
            f"- missed_tactic_rate: {latest.get('missed_tactic_rate', 0):.2%}",
            f"- opening played: {latest.get('opening_name', 'unknown')}",
        ]

    if instances_by_weakness:
        lines += ["", "Concrete instances of each PERSISTENT weakness (real data from this "
                  "player's own games -- reference these directly, do not invent others):"]
        for metric, instances in instances_by_weakness.items():
            if not instances:
                continue
            lines.append(f"\n{metric}:")
            for instance in instances:
                lines.append(
                    f"  - Game {instance['game_number']}, move {instance['move_number']}: "
                    f"{instance['explanation']}"
                )

    lines += [
        "",
        "Write a coaching report for this player as a chess coach would, in 3-5 short "
        "paragraphs. Use ONLY the data given above -- do not invent statistics, game "
        "details, opening names, or instances that are not listed. When discussing a "
        "persistent weakness that has concrete instances listed above, reference at "
        "least one of them by game and move number so the feedback feels personal, not "
        "generic. Explain what the recurring weaknesses mean in practical terms, note "
        "whether each looks transient or persistent based on the trend data, and end "
        "with encouraging, concrete guidance on what to focus on next.",
    ]
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
    vector_df: pd.DataFrame,
    ranked_weakness_tags: list[str],
    player_name: str,
    instances_by_weakness: dict[str, list[dict]] | None = None,
    model: str = DEFAULT_MODEL,
) -> dict:
    """Input shape: vector_df (trend-augmented weakness-vector DataFrame, chronologically
    sorted), ranked_weakness_tags list[str] (from weakness.aggregate.rank_weakness_tags),
    player_name str, instances_by_weakness optional dict[str, list[dict]] (from
    nlp.instances.build_instances_by_weakness; 2026-09-22 change request), model str.
    Output shape: dict {text_report: str, source: 'llm' | 'template_fallback'}.

    Purpose: the Phase 5B entry point. Tries the LLM path first; on any failure
    (missing API key, network error, bad response, empty text), logs a clear
    warning and falls back to the deterministic template report, so a coherent
    multi-paragraph report is always produced. instances_by_weakness is passed
    through to both paths so the narrative references concrete games/moves
    either way, not only in the LLM path.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        logger.warning("ANTHROPIC_API_KEY not set; falling back to template-based report.")
        return {
            "text_report": template_report(
                vector_df, ranked_weakness_tags, player_name, instances_by_weakness
            ),
            "source": "template_fallback",
        }

    prompt = build_report_prompt(vector_df, ranked_weakness_tags, player_name, instances_by_weakness)
    try:
        text = _call_anthropic_api(prompt, api_key, model=model)
        if not text.strip():
            raise ValueError("Anthropic API returned an empty response")
        return {"text_report": text, "source": "llm"}
    except Exception as exc:
        logger.warning(
            "LLM report generation failed (%s); falling back to template-based report.", exc
        )
        return {
            "text_report": template_report(
                vector_df, ranked_weakness_tags, player_name, instances_by_weakness
            ),
            "source": "template_fallback",
        }
