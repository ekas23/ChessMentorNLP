"""Per-game metadata from PGN headers, from the analysed player's point of view:
colour, opponent, result, ratings, time class, link, opening."""

from __future__ import annotations

import chess
import chess.pgn

from src.annotation.engine import player_color
from src.features.openings import classify_eco

TIME_CLASSES = ["bullet", "blitz", "rapid", "daily"]


def time_class_from_control(time_control: str | None) -> str | None:
    """Input: PGN TimeControl header ('180+2', '600', '1/86400', '-').
    Output: 'bullet' | 'blitz' | 'rapid' | 'daily' | None, using Chess.com's rule
    (estimated duration = base + 40 * increment: <180s bullet, <600s blitz, else rapid)."""
    if not time_control or time_control in ("-", "?"):
        return None
    if "/" in time_control:
        return "daily"
    try:
        base, _, inc = time_control.partition("+")
        seconds = int(base) + 40 * int(inc or 0)
    except ValueError:
        return None
    if seconds < 180:
        return "bullet"
    if seconds < 600:
        return "blitz"
    return "rapid"


def game_metadata(game: chess.pgn.Game, username: str | None) -> dict:
    """Input: game, analysed player's username.
    Output: dict with colour, opponent, result ('win'|'loss'|'draw'|None), player/opponent
    ratings, time_class, link, eco, opening_name, date."""
    h = game.headers
    color = player_color(game, username)
    opening = classify_eco(game)
    result_tag = h.get("Result", "*")
    if color is None:
        colour = opponent = result = player_rating = opp_rating = None
    else:
        is_white = color == chess.WHITE
        colour = "white" if is_white else "black"
        opponent = h.get("Black" if is_white else "White")
        player_rating = h.get("WhiteElo" if is_white else "BlackElo")
        opp_rating = h.get("BlackElo" if is_white else "WhiteElo")
        result = {"1-0": "win" if is_white else "loss",
                  "0-1": "loss" if is_white else "win",
                  "1/2-1/2": "draw"}.get(result_tag)
    return {
        "date": h.get("Date"),
        "colour": colour,
        "opponent": opponent,
        "result": result,
        "player_rating": player_rating,
        "opponent_rating": opp_rating,
        "time_class": h.get("TimeClass") or time_class_from_control(h.get("TimeControl")),
        "link": h.get("Link") or None,
        "eco": opening["eco"],
        "opening_name": opening["name"],
    }
