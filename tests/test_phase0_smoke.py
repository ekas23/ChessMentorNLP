"""Phase 0 smoke test: python-chess loads a PGN and Stockfish evaluates a position."""

import chess

from src.annotation.engine import analyse_position, create_engine
from src.config import RAW_PGN_DIR
from src.ingestion.parse_pgn import parse_pgn_file
from tests.helpers import requires_stockfish


def test_sample_pgn_loads():
    game = parse_pgn_file(str(RAW_PGN_DIR / "sample_game.pgn"))[0]
    assert len(list(game.mainline_moves())) == 38


@requires_stockfish
def test_stockfish_evaluates_starting_position_from_whites_view():
    engine = create_engine()
    try:
        cp, best = analyse_position(engine, chess.Board(), depth=10)
    finally:
        engine.quit()
    assert -150 < cp < 150  # roughly equal
    assert best is not None
