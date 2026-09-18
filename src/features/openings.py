"""ECO opening classification for the first 8-10 moves of a game.

Uses a small, curated table of well-known major opening families with their
standard ECO code ranges (verified against widely known chess opening theory)
rather than a full ECO database — sufficient to track a player's opening
repertoire trend over time without over-claiming precision on deep
sub-variations. Per Rules.md, this project never fabricates opening names:
every entry below is a genuine, standard opening family.
"""

import chess
import chess.pgn
import pandas as pd

# "first 8-10 moves" per Phases.md -> examine the first 10 half-moves (5 full moves).
MAX_PLY_FOR_ECO = 10

# tuple of leading SAN moves -> (eco_range, opening_name). Longest matching prefix wins.
_ECO_TABLE: dict[tuple[str, ...], tuple[str, str]] = {
    ("Nf3",): ("A04-A09", "Reti Opening"),
    ("c4",): ("A10-A39", "English Opening"),
    ("d4", "d5"): ("D00-D69", "Closed/Queen's Pawn Game"),
    ("d4", "Nf6", "c4", "g6"): ("E60-E99", "King's Indian Defense"),
    ("d4", "Nf6", "c4", "e6"): ("E20-E59", "Nimzo-/Queen's Indian family"),
    ("e4", "e6"): ("C00-C19", "French Defense"),
    ("e4", "c6"): ("B10-B19", "Caro-Kann Defense"),
    ("e4", "c5"): ("B20-B99", "Sicilian Defense"),
    ("e4", "e5"): ("C20-C99", "Open Game"),
    ("e4", "e5", "Nf3", "Nc6", "Bc4"): ("C50-C59", "Italian Game"),
    ("e4", "e5", "Nf3", "Nc6", "Bb5"): ("C60-C99", "Ruy Lopez"),
}


def classify_eco(game: chess.pgn.Game) -> dict:
    """Input shape: chess.pgn.Game.
    Output shape: dict {eco: str | None, name: str} — None/"Unknown/Irregular Opening"
    if no known prefix matches within the first MAX_PLY_FOR_ECO half-moves.

    Purpose: tag a game's opening family from its move order via longest-prefix
    match against `_ECO_TABLE`.
    """
    board = game.board()
    san_moves: list[str] = []
    for ply, move in enumerate(game.mainline_moves()):
        if ply >= MAX_PLY_FOR_ECO:
            break
        san_moves.append(board.san(move))
        board.push(move)

    best_match: tuple[tuple[str, ...], str, str] | None = None
    for prefix, (eco_range, name) in _ECO_TABLE.items():
        if len(prefix) <= len(san_moves) and tuple(san_moves[: len(prefix)]) == prefix:
            if best_match is None or len(prefix) > len(best_match[0]):
                best_match = (prefix, eco_range, name)

    if best_match is None:
        return {"eco": None, "name": "Unknown/Irregular Opening"}
    return {"eco": best_match[1], "name": best_match[2]}


def add_opening_columns(
    df: pd.DataFrame, games: list[chess.pgn.Game], game_ids: list[str]
) -> pd.DataFrame:
    """Input shape: df (pd.DataFrame with a 'game_id' column), games (list[chess.pgn.Game]),
    game_ids (list[str], same order/length as games — the ids assigned by
    annotation.engine.derive_game_id for the same games).
    Output shape: copy of df with 'eco' and 'opening_name' columns, constant per game_id.

    Purpose: attach the game-level opening classification to every move row
    belonging to that game.
    """
    eco_by_game_id = {
        game_id: classify_eco(game) for game_id, game in zip(game_ids, games, strict=True)
    }
    df = df.copy()
    df["eco"] = df["game_id"].map(lambda gid: eco_by_game_id.get(gid, {}).get("eco"))
    df["opening_name"] = df["game_id"].map(lambda gid: eco_by_game_id.get(gid, {}).get("name"))
    return df
