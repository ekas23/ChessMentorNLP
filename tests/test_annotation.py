"""Basic per-module tests for src/annotation/."""

import chess

from src.annotation.classify_moves import classify_move
from src.annotation.engine import derive_game_id
from src.ingestion.parse_pgn import parse_pgn_string

WHITE_TO_MOVE_FEN = chess.STARTING_FEN


def test_classify_move_labels_by_threshold():
    # White to move; eval drops 250cp for White -> blunder.
    assert classify_move(WHITE_TO_MOVE_FEN, 20, -230) == "blunder"
    assert classify_move(WHITE_TO_MOVE_FEN, 20, -90) == "mistake"
    assert classify_move(WHITE_TO_MOVE_FEN, 20, -35) == "inaccuracy"
    assert classify_move(WHITE_TO_MOVE_FEN, 20, 25) == "good"


def test_classify_move_accounts_for_black_to_move():
    black_fen = "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 2"
    # Black to move; eval swings +250cp (White gains) -> a blunder from Black's perspective.
    assert classify_move(black_fen, 0, 250) == "blunder"
    assert classify_move(black_fen, 0, -25) == "good"


def test_derive_game_id_uses_headers():
    game = parse_pgn_string(
        "[White \"Alice\"]\n[Black \"Bob\"]\n[Date \"2026.01.01\"]\n\n1. e4 e5 1-0\n"
    )[0]
    game_id = derive_game_id(game, 0)
    assert "Alice" in game_id and "Bob" in game_id


def test_derive_game_id_falls_back_to_index_without_headers():
    game = parse_pgn_string("1. e4 e5 1-0\n")[0]
    game_id = derive_game_id(game, 3)
    assert game_id == "game_3"
