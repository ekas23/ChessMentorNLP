"""Shared configuration constants used across pipeline layers."""

import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RAW_PGN_DIR = DATA_DIR / "raw_pgn"
ANNOTATED_DIR = DATA_DIR / "annotated"
WEAKNESS_VECTORS_DIR = DATA_DIR / "weakness_vectors"

_FALLBACK_STOCKFISH_PATHS = [
    "/usr/games/stockfish",
    "/usr/local/bin/stockfish",
    "/usr/bin/stockfish",
]


def resolve_stockfish_path() -> str:
    """Input shape: none. Output shape: str, absolute path to the Stockfish binary.

    Purpose: locate the Stockfish executable. Checks PATH first (via shutil.which),
    then falls back to common install locations (e.g. /usr/games/stockfish, where
    the Debian/Ubuntu `stockfish` apt package installs it without adding it to PATH).
    Raises FileNotFoundError with a clear message if no binary is found anywhere.
    """
    found = shutil.which("stockfish")
    if found:
        return found
    for candidate in _FALLBACK_STOCKFISH_PATHS:
        if Path(candidate).is_file():
            return candidate
    raise FileNotFoundError(
        "Stockfish binary not found on PATH or in known fallback locations "
        f"({_FALLBACK_STOCKFISH_PATHS}). Install it (e.g. `apt-get install stockfish`) "
        "or set its path explicitly."
    )
