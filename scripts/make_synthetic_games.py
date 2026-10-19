"""Generate synthetic test games: Stockfish at a low skill level ("TestPlayer")
against Stockfish at a higher level, alternating colours.

These games are ONLY for offline tests and demos (no network needed). They are
labelled [Event "Synthetic test game"] and must never be reported as real data.

Usage:
    python -m scripts.make_synthetic_games --games 24 --out data/raw_pgn/synthetic_games.pgn
"""

from __future__ import annotations

import argparse
import datetime as dt
import random

import chess
import chess.engine
import chess.pgn

from src.config import resolve_stockfish_path


def play_game(engine, weak_skill: int, strong_skill: int, weak_is_white: bool, rng: random.Random) -> chess.pgn.Game:
    board = chess.Board()
    # A couple of random opening moves so the games differ.
    for _ in range(rng.choice([0, 1, 2])):
        board.push(rng.choice(list(board.legal_moves)))
    while not board.is_game_over(claim_draw=True) and board.ply() < 160:
        weak_to_move = (board.turn == chess.WHITE) == weak_is_white
        engine.configure({"Skill Level": weak_skill if weak_to_move else strong_skill})
        result = engine.play(board, chess.engine.Limit(depth=6 if weak_to_move else 10))
        board.push(result.move)
    return chess.pgn.Game.from_board(board)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--games", type=int, default=24)
    parser.add_argument("--out", default="data/raw_pgn/synthetic_games.pgn")
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    engine = chess.engine.SimpleEngine.popen_uci(resolve_stockfish_path())
    start = dt.date(2026, 9, 1)
    try:
        with open(args.out, "w", encoding="utf-8") as fh:
            for i in range(args.games):
                weak_is_white = i % 2 == 0
                game = play_game(engine, weak_skill=rng.choice([1, 2, 3]), strong_skill=10,
                                 weak_is_white=weak_is_white, rng=rng)
                h = game.headers
                h["Event"] = "Synthetic test game"
                h["Site"] = "Local"
                h["Date"] = (start + dt.timedelta(days=i // 2)).strftime("%Y.%m.%d")
                h["Round"] = str(i + 1)
                h["White"] = "TestPlayer" if weak_is_white else f"Opponent{i % 5}"
                h["Black"] = f"Opponent{i % 5}" if weak_is_white else "TestPlayer"
                h["TimeControl"] = "600"
                print(game, file=fh, end="\n\n")
                print(f"game {i + 1}/{args.games}: {h['Result']} ({game.end().board().ply()} plies)")
    finally:
        engine.quit()


if __name__ == "__main__":
    main()
