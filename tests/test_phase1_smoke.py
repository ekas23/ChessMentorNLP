"""Phase 1 smoke test: data ingestion (PGN upload + API pull).

Done-when criteria (Phases.md, Phase 1): you can pull your own last N games
and get a list of parsed game objects.

Live network access to api.chess.com / lichess.org is blocked by this sandbox's
egress policy, so the API-pull path is verified against a mocked HTTP response
matching each API's real documented response shape rather than a live call.
The PGN-upload path is verified against real multi-game PGN data on disk,
including a deliberately malformed/empty game to confirm skip-and-log behavior.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.config import RAW_PGN_DIR  # noqa: E402
from src.ingestion.fetch_games import fetch_chess_com_games, fetch_lichess_games  # noqa: E402
from src.ingestion.parse_pgn import parse_pgn_file, parse_pgn_string  # noqa: E402

SAMPLE_PGN_ONE_GAME = """[Event "Sample"]
[White "A"]
[Black "B"]
[Result "1-0"]

1. e4 e5 2. Nf3 1-0
"""


def test_parse_pgn_file_skips_malformed_games() -> None:
    games = parse_pgn_file(str(RAW_PGN_DIR / "sample_multi_game.pgn"))
    print(f"parse_pgn_file: parsed {len(games)} valid game(s) from 3 raw entries "
          f"(1 deliberately empty/malformed)")
    assert len(games) == 2, f"Expected 2 valid games (1 empty game skipped), got {len(games)}"
    assert games[0].headers["Event"] == "Sample Game 1"
    assert games[1].headers["Event"] == "Sample Game 2"


def test_parse_pgn_string_basic() -> None:
    games = parse_pgn_string(SAMPLE_PGN_ONE_GAME)
    assert len(games) == 1
    assert len(list(games[0].mainline_moves())) == 3
    print("parse_pgn_string: parsed 1 game with 3 half-moves")


def test_fetch_chess_com_games_mocked() -> None:
    """Mocks requests.get to return Chess.com's real documented response shape:
    an archive-list JSON, then a per-month JSON with a 'games' list of PGN blobs.
    """
    archives_resp = MagicMock()
    archives_resp.raise_for_status = MagicMock()
    archives_resp.json.return_value = {
        "archives": ["https://api.chess.com/pub/player/testuser/games/2026/01"]
    }

    month_resp = MagicMock()
    month_resp.raise_for_status = MagicMock()
    month_resp.json.return_value = {"games": [{"pgn": SAMPLE_PGN_ONE_GAME}]}

    with patch("src.ingestion.fetch_games.requests.get", side_effect=[archives_resp, month_resp]):
        games = fetch_chess_com_games("testuser", max_games=5)

    print(f"fetch_chess_com_games (mocked): got {len(games)} game(s)")
    assert len(games) == 1
    assert games[0].headers["White"] == "A"


def test_fetch_lichess_games_mocked() -> None:
    """Mocks requests.get to return Lichess's real documented response shape:
    a raw PGN-text body (possibly multiple concatenated games).
    """
    lichess_resp = MagicMock()
    lichess_resp.raise_for_status = MagicMock()
    lichess_resp.text = SAMPLE_PGN_ONE_GAME

    with patch("src.ingestion.fetch_games.requests.get", return_value=lichess_resp):
        games = fetch_lichess_games("testuser", max_games=5)

    print(f"fetch_lichess_games (mocked): got {len(games)} game(s)")
    assert len(games) == 1
    assert games[0].headers["Black"] == "B"


def main() -> None:
    test_parse_pgn_file_skips_malformed_games()
    test_parse_pgn_string_basic()
    test_fetch_chess_com_games_mocked()
    test_fetch_lichess_games_mocked()
    print("\nPhase 1 smoke test PASSED: PGN upload path (live) and API pull path "
          "(mocked, real network blocked in this sandbox) both produce parsed game objects.")


if __name__ == "__main__":
    main()
