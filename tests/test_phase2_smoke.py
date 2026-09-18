"""Phase 2 smoke test: engine annotation + move quality classification.

Done-when criteria (Phases.md, Phase 2): a full game produces a labeled
move-by-move table with no crashes.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.annotation.classify_moves import QUALITY_LABELS  # noqa: E402
from src.annotation.engine import ANNOTATION_COLUMNS, annotate_games  # noqa: E402
from src.config import RAW_PGN_DIR  # noqa: E402
from src.ingestion.parse_pgn import parse_pgn_file  # noqa: E402

# Low depth keeps this smoke test fast; production runs should use a higher depth.
SMOKE_TEST_DEPTH = 8


def main() -> None:
    games = parse_pgn_file(str(RAW_PGN_DIR / "sample_short_game.pgn"))
    assert len(games) == 1, f"Expected 1 game, got {len(games)}"
    print(f"Loaded {len(games)} game(s) for annotation")

    df = annotate_games(games, depth=SMOKE_TEST_DEPTH)
    print(df.to_string(index=False))

    expected_moves = len(list(games[0].mainline_moves()))
    assert len(df) == expected_moves, f"Expected {expected_moves} rows, got {len(df)}"
    assert list(df.columns) == ANNOTATION_COLUMNS + ["quality_label"], (
        f"Column mismatch: {list(df.columns)}"
    )
    assert df["quality_label"].isin(QUALITY_LABELS).all(), "Unexpected quality label present"
    assert df["eval_before"].notna().all() and df["eval_after"].notna().all(), (
        "Found missing eval values"
    )

    print(f"\nPhase 2 smoke test PASSED: {len(df)} moves annotated and labeled, no crashes.")


if __name__ == "__main__":
    main()
