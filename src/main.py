"""End-to-end pipeline orchestration: Chess.com username + game count -> full
coaching report + training plan. CLI entry point per Architecture.md
(`argparse`; no web framework in the CLI itself, per Rules.md's constraint on
adding one only when a phase explicitly calls for a UI).

Single-input ingestion model (2026-09-21 scope change, see Memory.md): the
product surface (this CLI, and the webapp dashboard) takes exactly a
Chess.com username and a number of games -- no PGN file upload, no source
selection. run_pipeline() is that product-facing entry point.
"""

import argparse
import logging
import sys

from src.annotation.engine import DEFAULT_DEPTH, annotate_games, derive_game_id
from src.features.motifs import add_motif_column
from src.features.openings import add_opening_columns
from src.features.positional import add_positional_columns
from src.ingestion.fetch_games import (
    DEFAULT_N_GAMES,
    ChessComAPIError,
    ChessComNoPublicGamesError,
    ChessComUsernameNotFoundError,
    fetch_last_n_games,
)
from src.nlp.instances import build_instances_by_weakness
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


def run_pipeline(username: str, max_games: int = DEFAULT_N_GAMES, depth: int = DEFAULT_DEPTH) -> dict:
    """Input shape: username str (Chess.com handle), max_games int (how many of the
    player's most recent games to analyze; default 50), depth int (Stockfish search depth).
    Output shape: dict — see _run_pipeline_on_games() for the full shape.

    Purpose: the single, product-facing orchestration entry point. Fetches the
    player's most recent `max_games` public Chess.com games (see
    ingestion.fetch_games.fetch_last_n_games) and runs them through the rest of
    the pipeline. Lets ChessComUsernameNotFoundError / ChessComNoPublicGamesError
    / ChessComAPIError propagate to the caller (CLI/webapp), which is expected to
    catch them and show a clear message rather than a raw traceback (Rules.md §2)
    -- this function itself does not swallow them, since which message to show
    the user is a presentation-layer decision.
    """
    games = fetch_last_n_games(username, n=max_games)
    return _run_pipeline_on_games(games, player_name=username, depth=depth, requested_n=max_games)


def _run_pipeline_on_games(
    games: list, player_name: str, depth: int = DEFAULT_DEPTH, requested_n: int | None = None
) -> dict:
    """Input shape: games (list[chess.pgn.Game], already fetched/parsed), player_name str,
    depth int, requested_n optional int (how many games were asked for, only used to
    note in the result when fewer were available).
    Output shape: dict {text_report: str, report_source: 'llm' | 'template_fallback',
    training_plan: list[dict], games_analyzed: int, games_requested: int | None,
    persistent_weaknesses: list[str], ranked_weaknesses: list[str], timeline: list[dict]}
    — matches Architecture.md §4's final Recommendation->Output contract
    ({text_report, training_plan}), extended with run metadata for the CLI/report display.

    Purpose: the game-list-in, report-out core of the pipeline (annotation ->
    features -> weakness -> NLP -> recommendation), factored out from
    run_pipeline() so it can be exercised directly against a list of already-parsed
    games -- used by run_pipeline() for the live Chess.com path, and by tests to
    verify the pipeline end to end using local PGN fixtures without needing live
    network access (this module has no other file-upload/local-file entry point;
    see ingestion.parse_pgn.parse_pgn_file, which tests call directly to build the
    `games` list they pass in here). Raises RuntimeError if no games survive
    ingestion or annotation, per Rules.md's fail-fast rule.
    """
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

    # Concrete per-move examples for each PERSISTENT weakness only (2026-09-22 change
    # request) -- built from moves_df, the per-move annotated+featured data, which
    # already carries everything needed (fen, move_uci, motif_detail, quality_label).
    instances_by_weakness = build_instances_by_weakness(moves_df, trend_df, persistent)

    report = generate_coaching_report(trend_df, ranked_tags, player_name, instances_by_weakness)
    training_plan = build_training_plan(persistent, trend_df, instances_by_weakness)

    return {
        "text_report": report["text_report"],
        "report_source": report["source"],
        "training_plan": training_plan,
        "games_analyzed": len(trend_df),
        "games_requested": requested_n,
        "persistent_weaknesses": persistent,
        "ranked_weaknesses": ranked_tags,
        # Per-game rows (date, rates, trend columns), for the webapp dashboard's
        # timeline chart/table -- an additive extension, existing keys are unchanged.
        "timeline": trend_df.to_dict(orient="records"),
    }


def _print_result(result: dict) -> None:
    """Input shape: dict, the output of run_pipeline(). Output shape: None (prints to stdout).
    Purpose: render the pipeline's output as readable CLI text.
    """
    print("=" * 70)
    print(result["text_report"])
    print("=" * 70)
    coverage_note = ""
    requested = result.get("games_requested")
    if requested is not None and result["games_analyzed"] < requested:
        coverage_note = f" (this account has fewer than {requested} total games)"
    print(
        f"\n(report generated via: {result['report_source']}, "
        f"{result['games_analyzed']} games analyzed{coverage_note})\n"
    )
    print("Training Plan (persistent weaknesses only):")
    if not result["training_plan"]:
        print("  No persistent weaknesses identified yet -- analyze more games to build a plan.")
    for item in result["training_plan"]:
        print(f"\n[{item['weakness']}] ({item['training_type']}) -- persistent")
        print(f"  {item['description']}")
        for link in item["training_links"]:
            print(f"  -> {link}")
        if item.get("instances"):
            print("  Recurring instances:")
            for instance in item["instances"]:
                print(f"    - Game {instance['game_number']}, move {instance['move_number']} — {instance['explanation']}")
                for puzzle_link in instance.get("puzzle_links", []):
                    print(f"      -> Similar puzzle: {puzzle_link}")


def main() -> None:
    """Input shape: none (reads sys.argv via argparse). Output shape: None.
    Purpose: CLI entry point — one command takes a Chess.com username and a game
    count in, and produces a full report + training plan out. No PGN file upload
    and no source selection (Chess.com only) -- see Memory.md's 2026-09-21 entry.
    """
    parser = argparse.ArgumentParser(
        description="ChessMentorNLP: longitudinal weakness report + training plan"
    )
    parser.add_argument("--username", type=str, required=True, help="Chess.com username to pull games for")
    parser.add_argument(
        "--max-games", type=int, default=DEFAULT_N_GAMES,
        help=f"Number of most recent games to analyze (default {DEFAULT_N_GAMES})",
    )
    parser.add_argument("--depth", type=int, default=DEFAULT_DEPTH, help="Stockfish search depth")
    args = parser.parse_args()

    try:
        result = run_pipeline(username=args.username, max_games=args.max_games, depth=args.depth)
    except ChessComUsernameNotFoundError:
        logger.error("Chess.com username '%s' was not found. Check the spelling and try again.", args.username)
        sys.exit(1)
    except ChessComNoPublicGamesError:
        logger.error("'%s' has no public games available (private or empty profile).", args.username)
        sys.exit(1)
    except ChessComAPIError as exc:
        logger.error("Chess.com API request failed: %s", exc)
        sys.exit(1)
    except Exception as exc:
        logger.error("Pipeline failed: %s", exc)
        sys.exit(1)

    _print_result(result)


if __name__ == "__main__":
    main()
