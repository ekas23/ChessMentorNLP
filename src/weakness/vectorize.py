"""Per-game weakness vector construction from the annotated+featured move data.

Turns the per-move DataFrame (Architecture.md §4's Features output) into one
row per game summarizing rate-based weakness signals, per PRD.md's goal of
distinguishing persistent weaknesses from one-off mistakes.
"""

import chess.pgn
import pandas as pd

MISTAKE_LABELS = ["blunder", "mistake"]
GAME_PHASES = ["opening", "middlegame", "endgame"]


def build_weakness_vector(game_moves_df: pd.DataFrame, game_id: str, game_date: str | None) -> dict:
    """Input shape: game_moves_df (pd.DataFrame of annotated+featured move rows for exactly
    one game — game_id, quality_label, phase, pawn_structure, king_safety, motif, eco,
    opening_name columns), game_id str, game_date str | None (raw PGN Date header, e.g.
    "2026.01.01" or with "??" placeholders).
    Output shape: dict — one weakness-vector row (see module docstring for fields).

    Purpose: summarize a single game's move-by-move data into rate-based weakness
    signals suitable for cross-game longitudinal comparison. Raises ValueError if
    game_moves_df is empty — an empty game should never silently produce a vector
    of zeros/NaNs that looks like "no weaknesses" (Rules.md: fail fast, don't
    propagate missing data silently).
    """
    if game_moves_df.empty:
        raise ValueError(f"Cannot build a weakness vector for game '{game_id}': no move rows")

    n = len(game_moves_df)
    label_counts = game_moves_df["quality_label"].value_counts()

    vector = {
        "game_id": game_id,
        "date": game_date,
        "num_moves": n,
        "blunder_rate": label_counts.get("blunder", 0) / n,
        "mistake_rate": label_counts.get("mistake", 0) / n,
        "inaccuracy_rate": label_counts.get("inaccuracy", 0) / n,
        "pawn_weakness_rate": (game_moves_df["pawn_structure"] != "normal").mean(),
        "king_safety_avg": game_moves_df["king_safety"].mean(),
        "missed_tactic_rate": _missed_tactic_rate(game_moves_df),
        "eco": game_moves_df["eco"].iloc[0] if "eco" in game_moves_df.columns else None,
        "opening_name": (
            game_moves_df["opening_name"].iloc[0] if "opening_name" in game_moves_df.columns else None
        ),
    }
    for phase in GAME_PHASES:
        vector[f"{phase}_blunder_rate"] = _phase_mistake_rate(game_moves_df, phase)
    return vector


def vectorize_games(
    moves_df: pd.DataFrame, games: list[chess.pgn.Game], game_ids: list[str]
) -> pd.DataFrame:
    """Input shape: moves_df (the full annotated+featured DataFrame across all games),
    games (list[chess.pgn.Game]), game_ids (list[str], same order/length as games — the
    ids from annotation.engine.derive_game_id).
    Output shape: pd.DataFrame, one row per game (per Architecture.md §4's
    Weakness->NLP contract), in the same order as `games`.

    Purpose: batch entry point building the full weakness-vector table. A game with
    zero surviving move rows (e.g. it was skipped earlier in annotation) is logged
    and excluded rather than producing a degenerate all-NaN row.
    """
    rows = []
    for game_id, game in zip(game_ids, games, strict=True):
        game_moves_df = moves_df[moves_df["game_id"] == game_id]
        try:
            rows.append(build_weakness_vector(game_moves_df, game_id, game.headers.get("Date")))
        except ValueError:
            continue
    return pd.DataFrame(rows)


def _phase_mistake_rate(game_moves_df: pd.DataFrame, phase: str) -> float | None:
    """Input shape: game_moves_df (one game's move rows), phase str ('opening' |
    'middlegame' | 'endgame').
    Output shape: float in [0, 1], or None if the game never reached that phase.

    Purpose: fraction of moves within a given game phase that were a blunder or
    mistake — lets the report distinguish e.g. "blunders mostly in the endgame"
    from "blunders mostly in the opening".
    """
    phase_df = game_moves_df[game_moves_df["phase"] == phase]
    if phase_df.empty:
        return None
    return phase_df["quality_label"].isin(MISTAKE_LABELS).mean()


def _missed_tactic_rate(game_moves_df: pd.DataFrame) -> float:
    """Input shape: game_moves_df (one game's move rows, with 'motif' and 'quality_label').
    Output shape: float in [0, 1].

    Purpose: proxy for "missed tactical opportunities" — among positions where a
    fork/pin/skewer motif was geometrically present for the mover, what fraction
    were played as a blunder or mistake rather than capitalized on. Returns 0.0
    (not None) when no motif-bearing positions occurred, since "no opportunities,
    so none missed" is a meaningful zero rather than missing data.
    """
    motif_present = game_moves_df["motif"] != ""
    if motif_present.sum() == 0:
        return 0.0
    missed = motif_present & game_moves_df["quality_label"].isin(MISTAKE_LABELS)
    return missed.sum() / motif_present.sum()
