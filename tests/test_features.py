"""Basic per-module tests for src/features/."""

import chess

from src.features.motifs import detect_fork, detect_motifs, detect_pin
from src.features.openings import classify_eco
from src.features.positional import game_phase, king_safety, material_balance, pawn_structure
from src.ingestion.parse_pgn import parse_pgn_string


def test_material_balance_starting_position_is_zero():
    assert material_balance(chess.Board()) == 0


def test_material_balance_reflects_captured_piece():
    board = chess.Board()
    board.remove_piece_at(chess.D8)  # remove Black's queen
    assert material_balance(board) == 9


def test_pawn_structure_isolated():
    board = chess.Board("4k3/8/8/8/8/8/4P3/4K3 w - - 0 1")  # lone White e-pawn
    assert pawn_structure(board, chess.WHITE) == "isolated"


def test_pawn_structure_doubled():
    # Doubled e-pawns (e3, e4), but d3 keeps neither file isolated -- isolates 'doubled'
    # as the reported weakness rather than 'isolated' (which takes priority when present).
    board = chess.Board("4k3/8/8/8/4P3/3PP3/8/4K3 w - - 0 1")
    assert pawn_structure(board, chess.WHITE) == "doubled"


def test_pawn_structure_normal():
    board = chess.Board()
    assert pawn_structure(board, chess.WHITE) == "normal"


def test_king_safety_higher_when_shielded():
    shielded = chess.Board("4k3/8/8/8/8/8/PPP5/2K5 w - - 0 1")
    exposed = chess.Board("4k3/8/8/8/8/8/8/2K5 w - - 0 1")
    assert king_safety(shielded, chess.WHITE) > king_safety(exposed, chess.WHITE)


def test_game_phase_endgame_when_material_low():
    board = chess.Board("4k3/8/8/8/8/8/4P3/4K3 w - - 0 1")
    assert game_phase(board, move_number=40) == "endgame"


def test_game_phase_opening_early_with_full_material():
    assert game_phase(chess.Board(), move_number=2) == "opening"


def test_detect_fork_known_knight_fork():
    board = chess.Board("2r3k1/4Np1p/6p1/8/8/8/8/6K1 w - - 0 1")
    assert detect_fork(board) is True


def test_detect_pin_known_position():
    # White rook on e1 pins Black's knight on e5 to the Black king on e8.
    board = chess.Board("4k3/8/8/4n3/8/8/8/4RK2 w - - 0 1")
    assert detect_pin(board) is True


def test_detect_motifs_returns_list():
    board = chess.Board()
    assert detect_motifs(board) == []


def test_classify_eco_ruy_lopez():
    game = parse_pgn_string(
        "1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 4. Ba4 Nf6 5. O-O *\n"
    )[0]
    eco = classify_eco(game)
    assert eco["name"] == "Ruy Lopez"


def test_classify_eco_unknown_returns_none():
    game = parse_pgn_string("1. g4 e5 2. f3 *\n")[0]
    eco = classify_eco(game)
    assert eco["eco"] is None
    assert eco["name"] == "Unknown/Irregular Opening"
