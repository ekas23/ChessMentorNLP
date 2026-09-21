"""Tests for the local Flask dashboard (src/webapp/app.py).

Single-input model (2026-09-21 scope change, see Memory.md): the dashboard
takes a Chess.com username + game count only -- no file upload. Uses Flask's
test client with the Chess.com API mocked (no real server/socket, no live
network needed) to exercise the analyze flow and its error paths (missing
username, unknown username, private/empty profile, API failure).
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

from src.config import RAW_PGN_DIR
from src.webapp.app import app

SMOKE_TEST_DEPTH = 8


def _client():
    app.config["TESTING"] = True
    return app.test_client()


def _mock_chess_com_responses(pgn_text: str):
    archives_resp = MagicMock()
    archives_resp.status_code = 200
    archives_resp.ok = True
    archives_resp.json.return_value = {"archives": ["https://api.chess.com/pub/player/u/games/2026/01"]}

    month_resp = MagicMock()
    month_resp.status_code = 200
    month_resp.ok = True
    month_resp.json.return_value = {"games": [{"pgn": pgn_text}]}
    return [archives_resp, month_resp]


def test_index_page_loads():
    client = _client()
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"username" in resp.data.lower()
    assert b"pgn_file" not in resp.data  # upload path must be gone entirely


def test_analyze_with_no_username_shows_error():
    client = _client()
    resp = client.post("/analyze", data={})
    assert resp.status_code == 200
    assert b"Please enter a Chess.com username" in resp.data


def test_analyze_with_unknown_username_shows_clear_error():
    client = _client()
    not_found_resp = MagicMock()
    not_found_resp.status_code = 404
    with patch("src.ingestion.fetch_games.requests.get", return_value=not_found_resp):
        resp = client.post("/analyze", data={"username": "no_such_user_xyz", "max_games": "10"})
    assert resp.status_code == 200
    assert b"was not found" in resp.data


def test_analyze_with_empty_profile_shows_clear_error():
    client = _client()
    empty_archives_resp = MagicMock()
    empty_archives_resp.status_code = 200
    empty_archives_resp.ok = True
    empty_archives_resp.json.return_value = {"archives": []}
    with patch("src.ingestion.fetch_games.requests.get", return_value=empty_archives_resp):
        resp = client.post("/analyze", data={"username": "private_user", "max_games": "10"})
    assert resp.status_code == 200
    assert b"no public games available" in resp.data


def test_analyze_with_real_username_renders_report_and_training_plan():
    client = _client()
    pgn_text = (RAW_PGN_DIR / "sample_short_game.pgn").read_text()
    with patch("src.ingestion.fetch_games.requests.get", side_effect=_mock_chess_com_responses(pgn_text)):
        with patch("src.webapp.app.DASHBOARD_DEPTH", SMOKE_TEST_DEPTH):
            resp = client.post("/analyze", data={"username": "TestPlayer", "max_games": "5"})

    assert resp.status_code == 200
    body = resp.data.decode("utf-8")
    assert "Coaching Report" in body
    assert "Training Plan" in body
    assert "TestPlayer" in body


def test_analyze_reports_fewer_games_than_requested():
    client = _client()
    pgn_text = (RAW_PGN_DIR / "sample_short_game.pgn").read_text()
    with patch("src.ingestion.fetch_games.requests.get", side_effect=_mock_chess_com_responses(pgn_text)):
        with patch("src.webapp.app.DASHBOARD_DEPTH", SMOKE_TEST_DEPTH):
            resp = client.post("/analyze", data={"username": "TestPlayer", "max_games": "50"})

    body = resp.data.decode("utf-8")
    assert "fewer than 50 total" in body
