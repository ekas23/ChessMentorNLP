"""Opening name per game.

Chess.com already classifies every game: its PGN carries an [ECO "C50"] header
and an [ECOUrl "https://www.chess.com/openings/Italian-Game-Two-Knights-Defense"]
header. We use those first (accurate, deep classification). The small prefix
table below is only a fallback for PGNs without those headers (e.g. test
fixtures or other sites). The old version used ONLY a 11-entry table, which is
why most real games came out as "Unknown/Irregular Opening".
"""

from __future__ import annotations

import re

import chess.pgn

MAX_PLY_FOR_TABLE = 10

# Leading SAN moves -> (ECO range, family). Longest matching prefix wins.
_ECO_TABLE: dict[tuple[str, ...], tuple[str, str]] = {
    ("e4",): ("B00", "King's Pawn Opening"),
    ("d4",): ("A40", "Queen's Pawn Opening"),
    ("Nf3",): ("A04-A09", "Reti Opening"),
    ("c4",): ("A10-A39", "English Opening"),
    ("f4",): ("A02-A03", "Bird's Opening"),
    ("b3",): ("A01", "Nimzo-Larsen Attack"),
    ("g3",): ("A00", "Hungarian Opening"),
    ("e4", "e5"): ("C20", "Open Game"),
    ("e4", "c5"): ("B20-B99", "Sicilian Defense"),
    ("e4", "e6"): ("C00-C19", "French Defense"),
    ("e4", "c6"): ("B10-B19", "Caro-Kann Defense"),
    ("e4", "d5"): ("B01", "Scandinavian Defense"),
    ("e4", "d6"): ("B07-B09", "Pirc Defense"),
    ("e4", "g6"): ("B06", "Modern Defense"),
    ("e4", "Nf6"): ("B02-B05", "Alekhine's Defense"),
    ("e4", "Nc6"): ("B00", "Nimzowitsch Defense"),
    ("e4", "e5", "Nf3", "Nc6"): ("C44", "King's Knight Opening"),
    ("e4", "e5", "Nf3", "d6"): ("C41", "Philidor Defense"),
    ("e4", "e5", "Nf3", "Nf6"): ("C42-C43", "Petrov's Defense"),
    ("e4", "e5", "Nc3"): ("C25-C29", "Vienna Game"),
    ("e4", "e5", "f4"): ("C30-C39", "King's Gambit"),
    ("e4", "e5", "Bc4"): ("C23-C24", "Bishop's Opening"),
    ("e4", "e5", "Nf3", "Nc6", "Bc4"): ("C50-C59", "Italian Game"),
    ("e4", "e5", "Nf3", "Nc6", "Bb5"): ("C60-C99", "Ruy Lopez"),
    ("e4", "e5", "Nf3", "Nc6", "d4"): ("C44-C45", "Scotch Game"),
    ("e4", "e5", "Nf3", "Nc6", "Nc3"): ("C46-C49", "Four Knights Game"),
    ("d4", "d5"): ("D00", "Queen's Pawn Game"),
    ("d4", "d5", "c4"): ("D06-D69", "Queen's Gambit"),
    ("d4", "d5", "c4", "c6"): ("D10-D19", "Slav Defense"),
    ("d4", "d5", "c4", "e6"): ("D30-D69", "Queen's Gambit Declined"),
    ("d4", "d5", "c4", "dxc4"): ("D20-D29", "Queen's Gambit Accepted"),
    ("d4", "d5", "Bf4"): ("D00", "London System"),
    ("d4", "Nf6", "Bf4"): ("A45-A46", "London System"),
    ("d4", "Nf6"): ("A45", "Indian Defense"),
    ("d4", "Nf6", "c4", "g6"): ("E60-E99", "King's Indian Defense"),
    ("d4", "Nf6", "c4", "e6"): ("E00-E59", "Indian Game (Nimzo/Queen's/Catalan)"),
    ("d4", "Nf6", "c4", "c5"): ("A56-A79", "Benoni Defense"),
    ("d4", "Nf6", "c4", "g6", "Nc3", "d5"): ("D70-D99", "Grunfeld Defense"),
    ("d4", "f5"): ("A80-A99", "Dutch Defense"),
}


def name_from_eco_url(url: str) -> str | None:
    """Input: Chess.com ECOUrl. Output: readable opening name (move-order suffix dropped),
    e.g. '.../Italian-Game-Two-Knights-Defense-4.d3' -> 'Italian Game Two Knights Defense'."""
    if not url or "/openings/" not in url:
        return None
    slug = url.rstrip("/").split("/openings/")[-1]
    words = []
    for part in slug.split("-"):
        if re.search(r"\d", part) or "..." in part:
            break  # move-order suffix like '4.d3' or '3...Nf6'
        words.append(part)
    name = " ".join(words).strip()
    return name or None


def _table_lookup(game: chess.pgn.Game) -> tuple[str | None, str]:
    board = game.board()
    sans: list[str] = []
    for ply, move in enumerate(game.mainline_moves()):
        if ply >= MAX_PLY_FOR_TABLE:
            break
        sans.append(board.san(move))
        board.push(move)
    best = None
    for prefix, (eco, name) in _ECO_TABLE.items():
        if tuple(sans[: len(prefix)]) == prefix and (best is None or len(prefix) > len(best[0])):
            best = (prefix, eco, name)
    if best is None:
        return None, "Irregular Opening"
    return best[1], best[2]


def classify_eco(game: chess.pgn.Game) -> dict:
    """Input: game. Output: {'eco': code or range or None, 'name': opening name}."""
    eco_header = game.headers.get("ECO")
    url_name = name_from_eco_url(game.headers.get("ECOUrl", ""))
    if url_name:
        return {"eco": eco_header if eco_header and eco_header != "?" else None, "name": url_name}
    eco, name = _table_lookup(game)
    if eco_header and eco_header != "?":
        eco = eco_header
    return {"eco": eco, "name": name}
