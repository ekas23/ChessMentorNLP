"""Per-game weakness vectors, computed over the ANALYSED PLAYER'S moves only.

The previous version divided by every move in the game (both players), so the
opponent's mistakes were counted against the player. Every rate below is
(number of the player's moves showing the weakness) / (number of the player's
moves in the game).

Metrics (all per player move):
  blunder_rate, mistake_rate, inaccuracy_rate  -- quality labels (classify_moves.py)
  missed_tactic_rate  -- engine's best move created a fork/pin/skewer, the player
                         played something else, and it was a mistake or blunder
  pawn_weakness_rate  -- the move created a new isolated/doubled pawn for the player
                         AND was at least an inaccuracy (structural concessions that
                         the engine considers fine are not counted)
  {opening,middlegame,endgame}_blunder_rate -- blunders+mistakes within that phase
Games where the player made fewer than MIN_PLAYER_MOVES moves are excluded:
one blunder in a 4-move game would otherwise read as a 25% blunder rate.
"""

from __future__ import annotations

import logging

import chess.pgn
import pandas as pd

from src.annotation.classify_moves import MISTAKE_LABELS
from src.ingestion.game_meta import game_metadata

logger = logging.getLogger(__name__)

GAME_PHASES = ["opening", "middlegame", "endgame"]
MIN_PLAYER_MOVES = 10
WEAK_LABELS = ["blunder", "mistake", "inaccuracy"]


def player_moves(game_moves_df: pd.DataFrame) -> pd.DataFrame:
    """Input: one game's (or many games') move rows. Output: only the analysed player's rows."""
    if "is_player" not in game_moves_df.columns:
        return game_moves_df
    return game_moves_df[game_moves_df["is_player"].astype(bool)]


def is_pawn_weakness(df: pd.DataFrame) -> pd.Series:
    """Rows where the move created a pawn weakness that cost at least an inaccuracy."""
    return (df["pawn_weakness_created"].fillna("") != "") & df["quality_label"].isin(WEAK_LABELS)


def build_weakness_vector(game_moves_df: pd.DataFrame, game_id: str, meta: dict) -> dict | None:
    """Input: one game's annotated+featured rows, its id, its metadata (game_meta.game_metadata).
    Output: one weakness-vector row (dict), or None if the player made too few moves."""
    mine = player_moves(game_moves_df)
    n = len(mine)
    if n < MIN_PLAYER_MOVES:
        return None
    labels = mine["quality_label"].value_counts()
    vector = {
        "game_id": game_id,
        **meta,
        "num_player_moves": n,
        "blunder_rate": labels.get("blunder", 0) / n,
        "mistake_rate": labels.get("mistake", 0) / n,
        "inaccuracy_rate": labels.get("inaccuracy", 0) / n,
        "missed_tactic_rate": mine["missed_tactic"].astype(bool).sum() / n,
        "pawn_weakness_rate": is_pawn_weakness(mine).sum() / n,
        "king_safety_avg": mine["king_safety"].mean(),
    }
    for phase in GAME_PHASES:
        in_phase = mine[mine["phase"] == phase]
        vector[f"{phase}_blunder_rate"] = (
            None if in_phase.empty else in_phase["quality_label"].isin(MISTAKE_LABELS).mean()
        )
    return vector


def vectorize_games(
    moves_df: pd.DataFrame, games: list[chess.pgn.Game], game_ids: list[str], username: str | None = None
) -> tuple[pd.DataFrame, list[str]]:
    """Input: all move rows, the games, their ids, the analysed player's username.
    Output: (one row per kept game in input order, list of game_ids skipped as too short
    or missing annotation)."""
    rows, skipped = [], []
    for game_id, game in zip(game_ids, games, strict=True):
        game_rows = moves_df[moves_df["game_id"] == game_id]
        vector = None if game_rows.empty else build_weakness_vector(
            game_rows, game_id, game_metadata(game, username)
        )
        if vector is None:
            skipped.append(game_id)
            continue
        rows.append(vector)
    if skipped:
        logger.info("Excluded %d game(s) (too short or not annotated): %s", len(skipped), skipped)
    return pd.DataFrame(rows), skipped
