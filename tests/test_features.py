"""Motif detection, missed tactics, pawn-weakness events, phase, openings."""

import chess
import pandas as pd

from src.features.motifs import add_motif_column, motifs_created_by
from src.features.openings import classify_eco, name_from_eco_url
from src.features.positional import game_phase, pawn_weakness_created
from src.ingestion.game_meta import game_metadata, time_class_from_control
from src.ingestion.parse_pgn import parse_pgn_string
from src.annotation.classify_moves import classify_moves_df


def _types(fen, uci):
    return [m["type"] for m in motifs_created_by(chess.Board(fen), chess.Move.from_uci(uci))]


def test_knight_fork_of_king_and_rook():
    assert _types("r3k3/8/8/1N6/8/8/8/4K3 w - - 0 1", "b5c7") == ["fork"]


def test_skewer_of_king_with_queen_behind():
    assert _types("q7/8/8/k7/8/8/7R/4K3 w - - 0 1", "h2a2") == ["skewer"]


def test_absolute_pin():
    assert _types("4k3/3n4/8/8/8/8/4B3/4K3 w - - 0 1", "e2b5") == ["pin"]


def test_two_pawns_on_a_line_are_not_a_skewer():
    # The old detector called this a skewer ("pawn on d4 with a pawn on e5 behind it").
    assert _types("7k/8/8/4p3/3p4/8/8/B3K3 w - - 0 1", "a1b2") == []


def test_attacking_two_defended_cheaper_pieces_is_not_a_fork():
    assert _types("4k3/8/3p4/2n1n3/8/8/8/3QK3 w - - 0 1", "d1d4") == []


def test_attacking_two_undefended_pieces_is_a_fork():
    assert _types("4k3/8/8/2n1n3/8/8/8/3QK3 w - - 0 1", "d1d4") == ["fork"]


def _row(fen, played, best, wc_after_cp):
    df = pd.DataFrame([{"game_id": "g", "ply": 1, "move_number": 1, "side": "white", "is_player": True,
                        "fen": fen, "move_uci": played, "move_san": "", "eval_before": 0.0,
                        "eval_after": wc_after_cp, "best_move_uci": best, "best_reply_uci": None}])
    return add_motif_column(classify_moves_df(df)).iloc[0]


def test_missed_tactic_requires_engine_best_move_and_a_costly_alternative():
    fen = "r3k3/8/8/1N6/8/8/8/4K3 w - - 0 1"
    missed = _row(fen, "e1d2", "b5c7", -400)  # skipped the fork and it cost a lot
    assert missed["missed_tactic"] and missed["motif"] == "fork"
    assert missed["motif_detail"].startswith("Nc7+ would have forked")
    harmless = _row(fen, "e1d2", "b5c7", 0)  # skipped it but lost nothing
    assert not harmless["missed_tactic"]
    found = _row(fen, "b5c7", "b5c7", 0)  # played it
    assert found["motif"] == "" and not found["missed_tactic"]


def test_capture_that_isolates_pawns_is_an_event():
    board = chess.Board("4k3/8/8/8/8/2n5/PP6/4K3 w - - 0 1")  # bxc3 leaves a- and c-pawns isolated
    created = pawn_weakness_created(board, chess.Move.from_uci("b2c3"))
    assert "isolated pawn on the a-file" in created and "isolated pawn on the c-file" in created


def test_existing_weakness_is_not_counted_again():
    board = chess.Board("4k3/8/8/8/8/8/P7/4K3 w - - 0 1")  # a-pawn already isolated
    assert pawn_weakness_created(board, chess.Move.from_uci("e1f2")) == ""


def test_doubling_pawns_is_detected():
    board = chess.Board("4k3/8/8/8/8/3n4/2PP4/4K3 w - - 0 1")
    assert "doubled pawns on the d-file" in pawn_weakness_created(board, chess.Move.from_uci("c2d3"))


def test_phase_uses_full_move_number():
    assert game_phase(chess.Board(), 10) == "opening"
    assert game_phase(chess.Board(), 11) == "middlegame"
    assert game_phase(chess.Board("4k3/8/8/8/8/8/4P3/4K3 w - - 0 1"), 5) == "endgame"


def test_opening_name_from_chess_com_header():
    assert name_from_eco_url("https://www.chess.com/openings/Italian-Game-Two-Knights-Defense-4.d3") == \
        "Italian Game Two Knights Defense"
    game = parse_pgn_string('[ECO "B12"]\n[ECOUrl "https://www.chess.com/openings/Caro-Kann-Defense-Advance-Variation"]\n\n1. e4 c6 2. d4 d5 3. e5 *\n')[0]
    assert classify_eco(game) == {"eco": "B12", "name": "Caro Kann Defense Advance Variation"}


def test_opening_table_fallback_covers_common_first_moves():
    game = parse_pgn_string("1. d4 Nf6 2. Bf4 e6 *\n")[0]
    assert classify_eco(game)["name"] == "London System"


def test_time_class_rules():
    assert time_class_from_control("60") == "bullet"
    assert time_class_from_control("180+2") == "blitz"
    assert time_class_from_control("600") == "rapid"
    assert time_class_from_control("1/86400") == "daily"


def test_metadata_from_player_point_of_view():
    game = parse_pgn_string('[White "Bob"]\n[Black "Alice"]\n[Result "0-1"]\n[TimeControl "300"]\n\n1. e4 e5 0-1\n')[0]
    meta = game_metadata(game, "alice")
    assert (meta["colour"], meta["opponent"], meta["result"], meta["time_class"]) == ("black", "Bob", "win", "blitz")
