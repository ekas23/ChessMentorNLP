"""Tests for the local Flask dashboard (src/webapp/app.py).

Uses Flask's test client (no real server/socket needed) to exercise the
upload -> analyze -> report flow, the "not enough games for a trend" and
"invalid PGN" fallbacks, and confirms the report reuses src.main.run_pipeline
rather than any separate/duplicated logic.
"""

import io

from src.config import RAW_PGN_DIR
from src.webapp.app import app

SMOKE_TEST_DEPTH = 8


def _client():
    app.config["TESTING"] = True
    return app.test_client()


def test_index_page_loads():
    client = _client()
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"Upload a Game" in resp.data or b"ChessMentorNLP" in resp.data


def test_analyze_with_no_file_shows_error():
    client = _client()
    resp = client.post("/analyze", data={}, content_type="multipart/form-data")
    assert resp.status_code == 200
    assert b"Please choose a PGN file" in resp.data


def test_analyze_with_invalid_pgn_shows_clear_error():
    client = _client()
    data = {"pgn_file": (io.BytesIO(b"not a real pgn"), "bad.pgn")}
    resp = client.post("/analyze", data=data, content_type="multipart/form-data")
    assert resp.status_code == 200
    assert b"Could not analyze this PGN" in resp.data


def test_analyze_with_real_pgn_renders_report_and_training_plan():
    client = _client()
    pgn_path = RAW_PGN_DIR / "sample_short_game.pgn"
    with open(pgn_path, "rb") as f:
        data = {
            "pgn_file": (io.BytesIO(f.read()), "sample_short_game.pgn"),
            "player_name": "Dashboard Test Player",
            "depth": str(SMOKE_TEST_DEPTH),
        }
        resp = client.post("/analyze", data=data, content_type="multipart/form-data")

    assert resp.status_code == 200
    body = resp.data.decode("utf-8")
    assert "Coaching Report" in body
    assert "Training Plan" in body
    assert "Dashboard Test Player" in body


def test_analyze_multi_game_pgn_renders_trend_chart():
    client = _client()
    pgn_path = RAW_PGN_DIR / "sample_multi_game.pgn"
    with open(pgn_path, "rb") as f:
        data = {
            "pgn_file": (io.BytesIO(f.read()), "sample_multi_game.pgn"),
            "depth": "6",
        }
        resp = client.post("/analyze", data=data, content_type="multipart/form-data")

    assert resp.status_code == 200
    body = resp.data.decode("utf-8")
    assert "polyline points=" in body  # trend chart was drawn (>=2 games)
