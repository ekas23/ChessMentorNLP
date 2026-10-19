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
from src.features.positional import add_positional_columns
from src.ingestion.fetch_games import (
    DEFAULT_N_GAMES,
    ChessComAPIError,
    ChessComNoPublicGamesError,
    ChessComUsernameNotFoundError,
    fetch_last_n_games,
)
from src.ingestion.game_meta import TIME_CLASSES
from src.nlp.instances import build_instances_by_weakness
from src.nlp.report_generator import generate_coaching_report
from src.recommend.recommender import build_training_plan
from src.weakness.aggregate import (
    add_rolling_trends,
    identify_persistent_weaknesses,
    persistence_diagnostics,
    rank_weakness_tags,
    sort_chronologically,
)
from src.weakness.vectorize import vectorize_games

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def run_pipeline(
    username: str, max_games: int = DEFAULT_N_GAMES, depth: int = DEFAULT_DEPTH, time_class: str | None = None
) -> dict:
    """Input: Chess.com username, number of recent games, Stockfish depth, optional
    time-class filter. Output: see analyse_games(). Chess.com errors propagate so the
    CLI/web layer can show a clear message."""
    games = fetch_last_n_games(username, n=max_games, time_class=time_class)
    return analyse_games(games, username=username, depth=depth, requested_n=max_games, time_class=time_class)


def analyse_games(
    games: list,
    username: str | None,
    depth: int = DEFAULT_DEPTH,
    requested_n: int | None = None,
    time_class: str | None = None,
    use_cache: bool = True,
    return_moves: bool = False,
) -> dict:
    """Input: parsed games, the analysed player's username (None = treat every move as
    the player's; only for colour-less fixtures), depth, the number requested, the
    time-class filter used, cache flag, whether to include the per-move table.
    Output: dict {text_report, report_source, training_plan, games_analyzed,
    games_requested, games_skipped, time_class, persistent_weaknesses,
    ranked_weaknesses, diagnostics, timeline[, moves]}.

    Purpose: everything after ingestion. Used by run_pipeline(), the evaluation
    scripts (cohort, split-half) and the tests (local PGN fixtures)."""
    if not games:
        raise RuntimeError("No valid games were ingested; cannot build a report")
    game_ids = [derive_game_id(game, i) for i, game in enumerate(games)]

    moves_df = annotate_games(games, depth=depth, username=username, game_ids=game_ids, use_cache=use_cache)
    if moves_df.empty:
        raise RuntimeError("No games could be annotated; cannot build a report")
    moves_df = add_positional_columns(moves_df)
    moves_df = add_motif_column(moves_df)

    vector_df, skipped = vectorize_games(moves_df, games, game_ids, username)
    if vector_df.empty:
        raise RuntimeError("Every game was too short to analyse; cannot build a report")

    trend_df = add_rolling_trends(sort_chronologically(vector_df))
    diagnostics = persistence_diagnostics(trend_df)
    persistent = identify_persistent_weaknesses(trend_df)
    ranked = rank_weakness_tags(trend_df, persistent)
    instances = build_instances_by_weakness(moves_df, trend_df, persistent)

    report = generate_coaching_report(trend_df, persistent, diagnostics, username or "this player",
                                      instances, time_class, len(skipped))
    result = {
        "text_report": report["text_report"],
        "report_source": report["source"],
        "training_plan": build_training_plan(persistent, trend_df, instances),
        "games_analyzed": len(trend_df),
        "games_requested": requested_n,
        "games_skipped": len(skipped),
        "time_class": time_class or "all",
        "persistent_weaknesses": persistent,
        "ranked_weaknesses": ranked,
        "diagnostics": diagnostics,
        "timeline": trend_df.to_dict(orient="records"),
    }
    if return_moves:
        result["moves"] = moves_df
    return result


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
            print(f"  -> {link['label']}: {link['url']}")
        if item.get("instances"):
            print("  Recurring instances:")
            for instance in item["instances"]:
                print(f"    - Game {instance['game_number']}, {instance['move_label']}: {instance['explanation']}")
                print(f"      position: {instance['position_url']}")
                for link in instance.get("practice_links", []):
                    print(f"      practise: {link['label']} {link['url']}")


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
    parser.add_argument("--time-class", choices=["all", *TIME_CLASSES], default="all",
                        help="Only analyse games of this time control (default: all)")
    args = parser.parse_args()

    try:
        result = run_pipeline(username=args.username, max_games=args.max_games, depth=args.depth,
                              time_class=None if args.time_class == "all" else args.time_class)
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
