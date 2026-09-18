"""Phase 0 smoke test: verify the toolchain works end-to-end on a trivial example.

Done-when criteria (Phases.md, Phase 0): a sample PGN can be loaded and one
position can be evaluated by Stockfish.
"""

import sys
from pathlib import Path

import chess
import chess.pgn
from stockfish import Stockfish

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.config import RAW_PGN_DIR, resolve_stockfish_path  # noqa: E402


def load_sample_game() -> chess.pgn.Game:
    """Input shape: none (reads data/raw_pgn/sample_game.pgn).
    Output shape: a single chess.pgn.Game object.
    Purpose: verify python-chess can parse a PGN file from disk.
    """
    pgn_path = RAW_PGN_DIR / "sample_game.pgn"
    with open(pgn_path, encoding="utf-8") as f:
        game = chess.pgn.read_game(f)
    if game is None:
        raise ValueError(f"Failed to parse PGN at {pgn_path}")
    return game


def evaluate_starting_position(stockfish_path: str) -> dict:
    """Input shape: str, path to the Stockfish binary.
    Output shape: dict, Stockfish's evaluation of the standard starting position
    (e.g. {'type': 'cp', 'value': 20}).
    Purpose: verify the Stockfish binary can be launched and returns an evaluation.
    """
    engine = Stockfish(path=stockfish_path, depth=10)
    engine.set_fen_position(chess.STARTING_FEN)
    return engine.get_evaluation()


def main() -> None:
    game = load_sample_game()
    move_count = len(list(game.mainline_moves()))
    print(f"Loaded sample PGN: '{game.headers.get('Event')}' — {move_count} half-moves")
    assert move_count > 0, "Parsed game has no moves"

    sf_path = resolve_stockfish_path()
    print(f"Resolved Stockfish binary at: {sf_path}")

    evaluation = evaluate_starting_position(sf_path)
    print(f"Stockfish evaluation of the starting position: {evaluation}")
    assert evaluation is not None and "value" in evaluation, "No evaluation returned"

    print("\nPhase 0 smoke test PASSED: PGN loads and Stockfish evaluates a position.")


if __name__ == "__main__":
    main()
