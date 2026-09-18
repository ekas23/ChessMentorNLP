"""End-to-end pipeline orchestration: username or PGN file -> full coaching
report + training plan. CLI entry point per Architecture.md (`argparse`; no
web framework, per Rules.md's constraint on adding one only when a phase
explicitly calls for a UI).
"""

import argparse
import logging
import sys

from src.annotation.engine import DEFAULT_DEPTH, annotate_games, derive_game_id
from src.features.motifs import add_motif_column
from src.features.openings import add_opening_columns
from src.features.positional import add_positional_columns
from src.ingestion.fetch_games import fetch_games
from src.ingestion.parse_pgn import parse_pgn_file
from src.nlp.report_generator import generate_coaching_report
from src.recommend.recommender import build_training_plan
from src.weakness.aggregate import (
    add_rolling_trends,
    identify_persistent_weaknesses,
    rank_weakness_tags,
    sort_chronologically,
)
from src.weakness.vectorize import vectorize_games

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def run_pipeline(
    username: str | None = None,
    source: str = "chess.com",
    pgn_file: str | None = None,
    max_games: int = 20,
    depth: int = DEFAULT_DEPTH,
) -> dict:
    """Input shape: username optional str (for an API pull by handle), source str
    ('chess.com' | 'lichess'), pgn_file optional str (path to a local PGN file, used
    instead of an API pull when given), max_games int, depth int (Stockfish search depth).
    Output shape: dict {text_report: str, report_source: 'llm' | 'template_fallback',
    training_plan: list[dict], games_analyzed: int, persistent_weaknesses: list[str],
    ranked_weaknesses: list[str]} — matches Architecture.md §4's final
    Recommendation->Output contract ({text_report, training_plan}), extended with
    run metadata useful for the CLI/report display.

    Purpose: the single orchestration entry point wiring ingestion -> annotation ->
    features -> weakness -> NLP -> recommendation end to end, with no manual steps
    in between (Phases.md Phase 7 done-when criterion). Raises ValueError if neither
    username nor pgn_file is given, and RuntimeError if no games survive ingestion or
    annotation, per Rules.md's fail-fast-rather-than-silently-propagate-nothing rule.
    """
    if pgn_file:
        games = parse_pgn_file(pgn_file)
        player_name = username or "Uploaded Games"
    elif username:
        games = fetch_games(username, source=source, max_games=max_games)
        player_name = username
    else:
        raise ValueError("Either username or pgn_file must be provided")

    if not games:
        raise RuntimeError("No valid games were ingested; cannot build a report")

    game_ids = [derive_game_id(game, i) for i, game in enumerate(games)]

    moves_df = annotate_games(games, depth=depth)
    moves_df = add_positional_columns(moves_df)
    moves_df = add_motif_column(moves_df)
    moves_df = add_opening_columns(moves_df, games, game_ids)

    vector_df = vectorize_games(moves_df, games, game_ids)
    if vector_df.empty:
        raise RuntimeError("No games survived annotation; cannot build a report")

    vector_df = sort_chronologically(vector_df)
    trend_df = add_rolling_trends(vector_df)
    persistent = identify_persistent_weaknesses(trend_df)
    ranked_tags = rank_weakness_tags(trend_df, persistent)

    report = generate_coaching_report(trend_df, ranked_tags, player_name)
    training_plan = build_training_plan(ranked_tags, trend_df)

    return {
        "text_report": report["text_report"],
        "report_source": report["source"],
        "training_plan": training_plan,
        "games_analyzed": len(trend_df),
        "persistent_weaknesses": persistent,
        "ranked_weaknesses": ranked_tags,
    }


def _print_result(result: dict) -> None:
    """Input shape: dict, the output of run_pipeline(). Output shape: None (prints to stdout).
    Purpose: render the pipeline's output as readable CLI text.
    """
    print("=" * 70)
    print(result["text_report"])
    print("=" * 70)
    print(
        f"\n(report generated via: {result['report_source']}, "
        f"{result['games_analyzed']} games analyzed)\n"
    )
    print("Training Plan:")
    for item in result["training_plan"]:
        print(f"\n[{item['weakness']}] ({item['training_type']})")
        print(f"  {item['description']}")
        for link in item["training_links"]:
            print(f"  -> {link}")


def main() -> None:
    """Input shape: none (reads sys.argv via argparse). Output shape: None.
    Purpose: CLI entry point — one command takes a username (or local PGN file) in
    and produces a full report + training plan out.
    """
    parser = argparse.ArgumentParser(
        description="ChessMentorNLP: longitudinal weakness report + training plan"
    )
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument(
        "--username", type=str, help="Chess.com/Lichess username to pull games for"
    )
    source_group.add_argument(
        "--pgn-file", type=str, help="Path to a local PGN file to analyze instead of an API pull"
    )
    parser.add_argument(
        "--source", type=str, default="chess.com", choices=["chess.com", "lichess"],
        help="Which API to pull from when --username is given",
    )
    parser.add_argument("--max-games", type=int, default=20)
    parser.add_argument("--depth", type=int, default=DEFAULT_DEPTH, help="Stockfish search depth")
    args = parser.parse_args()

    try:
        result = run_pipeline(
            username=args.username,
            source=args.source,
            pgn_file=args.pgn_file,
            max_games=args.max_games,
            depth=args.depth,
        )
    except Exception as exc:
        logger.error("Pipeline failed: %s", exc)
        sys.exit(1)

    _print_result(result)


if __name__ == "__main__":
    main()
