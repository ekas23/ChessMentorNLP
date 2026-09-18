"""Basic per-module tests for src/ingestion/."""

from unittest.mock import MagicMock, patch

from src.config import RAW_PGN_DIR
from src.ingestion.fetch_games import fetch_chess_com_games, fetch_lichess_games
from src.ingestion.parse_pgn import parse_pgn_file, parse_pgn_string

ONE_GAME_PGN = """[Event "Sample"]
[White "A"]
[Black "B"]
[Result "1-0"]

1. e4 e5 2. Nf3 1-0
"""


def test_parse_pgn_string_returns_one_game():
    games = parse_pgn_string(ONE_GAME_PGN)
    assert len(games) == 1
    assert len(list(games[0].mainline_moves())) == 3


def test_parse_pgn_file_skips_malformed_games():
    games = parse_pgn_file(str(RAW_PGN_DIR / "sample_multi_game.pgn"))
    assert len(games) == 2


def test_fetch_chess_com_games_mocked():
    archives_resp = MagicMock()
    archives_resp.json.return_value = {"archives": ["https://api.chess.com/pub/player/u/games/2026/01"]}
    month_resp = MagicMock()
    month_resp.json.return_value = {"games": [{"pgn": ONE_GAME_PGN}]}
    with patch("src.ingestion.fetch_games.requests.get", side_effect=[archives_resp, month_resp]):
        games = fetch_chess_com_games("u", max_games=5)
    assert len(games) == 1


def test_fetch_chess_com_games_returns_empty_on_request_failure():
    import requests

    with patch("src.ingestion.fetch_games.requests.get", side_effect=requests.exceptions.ConnectionError):
        games = fetch_chess_com_games("u", max_games=5)
    assert games == []


def test_fetch_lichess_games_mocked():
    resp = MagicMock()
    resp.text = ONE_GAME_PGN
    with patch("src.ingestion.fetch_games.requests.get", return_value=resp):
        games = fetch_lichess_games("u", max_games=5)
    assert len(games) == 1
