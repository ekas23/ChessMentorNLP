"""Move labelling and engine annotation.

These tests pin down the two bugs found on 2026-10-19: evaluations read from the
wrong perspective (mainline opening theory came out as blunders) and huge
mate-score swings."""

import chess
import pytest

from src.annotation.classify_moves import classify_move, win_chance, win_chance_drop
from src.annotation.engine import MATE_SCORE_CP, annotate_games, player_color
from src.config import RAW_PGN_DIR
from src.ingestion.parse_pgn import parse_pgn_file, parse_pgn_string
from tests.helpers import requires_stockfish, rows_from_moves


def test_win_chance_is_symmetric_and_bounded():
    assert win_chance(0) == pytest.approx(0)
    assert win_chance(300) == pytest.approx(-win_chance(-300))
    assert -1 < win_chance(-5000) < win_chance(5000) < 1


def test_black_move_scored_from_blacks_point_of_view():
    # White-POV eval goes from 0 to +400 after a Black move: that is bad for Black.
    assert classify_move("black", 0, 400) == "blunder"
    # Same numbers after a White move are good for White.
    assert classify_move("white", 0, 400) == "good"


def test_moves_in_decided_positions_are_not_blunders():
    # Both moves lose 300 cp, but +900 -> +600 is still completely winning (at most an
    # inaccuracy), whereas 0 -> -300 throws away a level game (a blunder).
    assert classify_move("white", 900, 600) in ("good", "inaccuracy")
    assert win_chance_drop("white", 900, 600) < 0.2
    assert classify_move("white", 0, -300) == "blunder"


def test_playing_the_engine_best_move_is_never_an_error():
    df = rows_from_moves(["e4"], [30, -300], best=["e2e4"])  # noisy drop, but it was the best move
    assert df["quality_label"].iloc[0] == "good"


def test_player_color_matches_headers_case_insensitively():
    game = parse_pgn_string('[White "Alice"]\n[Black "Bob"]\n\n1. e4 e5 *\n')[0]
    assert player_color(game, "alice") == chess.WHITE
    assert player_color(game, "BOB") == chess.BLACK
    assert player_color(game, "carol") is None


@requires_stockfish
def test_opening_theory_is_not_labelled_as_blunders():
    """Ruy Lopez main line: every move is standard theory. The old code labelled
    9 of these 38 moves blunders and 19 mistakes."""
    games = parse_pgn_file(str(RAW_PGN_DIR / "sample_game.pgn"))
    df = annotate_games(games, depth=12, username="Player A", use_cache=False)
    assert len(df) == 38
    assert (df["quality_label"] == "blunder").sum() == 0
    assert (df["quality_label"] == "mistake").sum() <= 1
    assert df["is_player"].sum() == 19  # only White's moves belong to Player A
    assert df["eval_before"].abs().max() <= MATE_SCORE_CP


@requires_stockfish
def test_checkmate_is_scored_as_a_win_for_the_mating_side():
    game = parse_pgn_string('[White "W"]\n[Black "B"]\n\n1. f3 e5 2. g4 Qh4# 0-1\n')[0]
    df = annotate_games([game], depth=8, username="B", use_cache=False)
    last = df.iloc[-1]
    assert last["eval_after"] == -MATE_SCORE_CP  # Black delivered mate
    assert last["quality_label"] == "good"
    assert df[df["move_san"] == "g4"]["quality_label"].iloc[0] == "blunder"  # g4?? allows mate
