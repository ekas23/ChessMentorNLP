"""Basic per-module tests for src/ingestion/."""

from unittest.mock import MagicMock, patch

import pytest

from src.config import RAW_PGN_DIR
from src.ingestion.fetch_games import (
    ChessComAPIError,
    ChessComNoPublicGamesError,
    ChessComUsernameNotFoundError,
    fetch_chess_com_games,
    fetch_last_n_games,
    fetch_lichess_games,
)
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


def _game_pgn(event_name: str) -> str:
    return f'[Event "{event_name}"]\n[White "A"]\n[Black "B"]\n[Result "1-0"]\n\n1. e4 e5 1-0\n'


def _ok_response(payload: dict) -> MagicMock:
    resp = MagicMock()
    resp.status_code = 200
    resp.ok = True
    resp.json.return_value = payload
    return resp


def test_fetch_last_n_games_selects_most_recent_n_oldest_to_newest():
    # One month with 3 games, chronological oldest->newest as the real API returns them.
    archives_resp = _ok_response({"archives": ["https://api.chess.com/pub/player/u/games/2026/01"]})
    month_resp = _ok_response(
        {"games": [{"pgn": _game_pgn("Game1")}, {"pgn": _game_pgn("Game2")}, {"pgn": _game_pgn("Game3")}]}
    )
    with patch("src.ingestion.fetch_games.requests.get", side_effect=[archives_resp, month_resp]):
        games = fetch_last_n_games("u", n=2)

    assert len(games) == 2
    assert [g.headers["Event"] for g in games] == ["Game2", "Game3"]  # oldest->newest of the most recent 2


def test_fetch_last_n_games_returns_all_when_fewer_than_n_available():
    archives_resp = _ok_response({"archives": ["https://api.chess.com/pub/player/u/games/2026/01"]})
    month_resp = _ok_response({"games": [{"pgn": ONE_GAME_PGN}]})
    with patch("src.ingestion.fetch_games.requests.get", side_effect=[archives_resp, month_resp]):
        games = fetch_last_n_games("u", n=50)
    assert len(games) == 1


def test_fetch_last_n_games_raises_username_not_found_on_404():
    not_found = MagicMock()
    not_found.status_code = 404
    with patch("src.ingestion.fetch_games.requests.get", return_value=not_found):
        with pytest.raises(ChessComUsernameNotFoundError):
            fetch_last_n_games("no_such_user", n=10)


def test_fetch_last_n_games_raises_no_public_games_on_empty_archives():
    empty_archives = _ok_response({"archives": []})
    with patch("src.ingestion.fetch_games.requests.get", return_value=empty_archives):
        with pytest.raises(ChessComNoPublicGamesError):
            fetch_last_n_games("private_user", n=10)


def test_fetch_last_n_games_retries_once_then_succeeds():
    import requests

    archives_resp = _ok_response({"archives": ["https://api.chess.com/pub/player/u/games/2026/01"]})
    month_resp = _ok_response({"games": [{"pgn": ONE_GAME_PGN}]})
    # First call to the archives endpoint fails, second (the retry) succeeds.
    with patch(
        "src.ingestion.fetch_games.requests.get",
        side_effect=[requests.exceptions.ConnectionError, archives_resp, month_resp],
    ), patch("time.sleep"):
        games = fetch_last_n_games("u", n=5)
    assert len(games) == 1


def test_fetch_last_n_games_raises_api_error_after_retry_exhausted():
    import requests

    with patch(
        "src.ingestion.fetch_games.requests.get", side_effect=requests.exceptions.ConnectionError
    ), patch("time.sleep"):
        with pytest.raises(ChessComAPIError):
            fetch_last_n_games("u", n=5)


def test_fetch_last_n_games_filters_time_class_skips_variants_and_keeps_links():
    archives_resp = _ok_response({"archives": ["https://api.chess.com/pub/player/u/games/2026/01"]})
    month_resp = _ok_response({"games": [
        {"pgn": _game_pgn("Blitz1"), "time_class": "blitz", "rules": "chess", "url": "https://www.chess.com/game/live/1"},
        {"pgn": _game_pgn("Rapid1"), "time_class": "rapid", "rules": "chess", "url": "https://www.chess.com/game/live/2"},
        {"pgn": _game_pgn("960"), "time_class": "rapid", "rules": "chess960", "url": "https://www.chess.com/game/live/3"},
        {"pgn": _game_pgn("Rapid2"), "time_class": "rapid", "rules": "chess", "url": "https://www.chess.com/game/live/4"},
    ]})
    with patch("src.ingestion.fetch_games.requests.get", side_effect=[archives_resp, month_resp]):
        games = fetch_last_n_games("U", n=10, time_class="rapid")
    assert [g.headers["Event"] for g in games] == ["Rapid1", "Rapid2"]
    assert games[0].headers["TimeClass"] == "rapid"
    assert games[1].headers["Link"] == "https://www.chess.com/game/live/4"
