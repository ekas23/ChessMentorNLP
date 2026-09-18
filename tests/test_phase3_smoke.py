"""Phase 3 smoke test: positional features, motif tags, and ECO opening classification.

Done-when criteria (Phases.md, Phase 3): every move row has full positional
features + motif tags where applicable.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.annotation.engine import annotate_games, derive_game_id  # noqa: E402
from src.config import RAW_PGN_DIR  # noqa: E402
from src.features.motifs import add_motif_column, detect_fork  # noqa: E402
from src.features.openings import add_opening_columns, classify_eco  # noqa: E402
from src.features.positional import add_positional_columns  # noqa: E402
from src.ingestion.parse_pgn import parse_pgn_file  # noqa: E402

import chess  # noqa: E402

SMOKE_TEST_DEPTH = 8


def test_fork_detection_on_known_position() -> None:
    """A knight on d5 forking the queen on d8's-file king and a rook is a textbook
    fork position; use it to sanity-check detect_fork() directly against a known case.
    """
    # White knight on e7 forks the king on g8 and the rook on c8 (classic smothered-mate setup).
    board = chess.Board("2r3k1/4Np1p/6p1/8/8/8/8/6K1 w - - 0 1")
    assert detect_fork(board) is True, "Expected a fork to be detected on a known forking position"
    print("detect_fork: correctly identified a known fork position")


def main() -> None:
    test_fork_detection_on_known_position()

    games = parse_pgn_file(str(RAW_PGN_DIR / "sample_game.pgn"))
    assert len(games) == 1
    game_ids = [derive_game_id(games[0], 0)]

    df = annotate_games(games, depth=SMOKE_TEST_DEPTH)
    df = add_positional_columns(df)
    df = add_motif_column(df)
    df = add_opening_columns(df, games, game_ids)

    print(df[["move_number", "material_balance", "king_safety", "pawn_structure", "phase", "motif"]].to_string(index=False))

    expected_columns = {
        "game_id", "move_number", "fen", "move_uci", "eval_before", "eval_after",
        "quality_label", "material_balance", "king_safety", "pawn_structure", "phase",
        "motif", "eco", "opening_name",
    }
    assert expected_columns.issubset(set(df.columns)), f"Missing columns: {expected_columns - set(df.columns)}"
    assert df["material_balance"].notna().all()
    assert df["king_safety"].notna().all()
    assert df["pawn_structure"].isin(["isolated", "doubled", "normal"]).all()
    assert df["phase"].isin(["opening", "middlegame", "endgame"]).all()
    assert df["motif"].notna().all()  # empty string is fine, but never null

    eco = classify_eco(games[0])
    print(f"\nOpening classification: {eco}")
    assert eco["name"] == "Ruy Lopez", f"Expected Ruy Lopez for this game, got {eco}"
    assert (df["opening_name"] == "Ruy Lopez").all()

    print(f"\nPhase 3 smoke test PASSED: {len(df)} rows all have full positional features, "
          f"motif tags, and correct opening classification.")


if __name__ == "__main__":
    main()
