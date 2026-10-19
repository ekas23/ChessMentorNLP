"""RQ4 step 1: build the two report versions for each user-study participant.

For each participant's Chess.com username this writes two plain-text reports:
the grounded ChessMentorNLP report and the statistics-only baseline. They are
labelled "Report A" / "Report B" in a random order per participant; the hidden
mapping goes to key.csv (do not show it to participants).

Usage:
    python -m scripts.make_study_reports --participants participants.csv --time-class rapid
where participants.csv has columns: participant_id,username
"""

from __future__ import annotations

import argparse
import random
from pathlib import Path

import pandas as pd

from src.ingestion.fetch_games import fetch_last_n_games
from src.main import analyse_games
from src.nlp.templates import baseline_report, metric_label


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--participants", required=True)
    ap.add_argument("--games", type=int, default=50)
    ap.add_argument("--time-class", default="rapid")
    ap.add_argument("--depth", type=int, default=14)
    ap.add_argument("--out", default="data/evaluation/study")
    ap.add_argument("--seed", type=int, default=2026)
    args = ap.parse_args()

    rng = random.Random(args.seed)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    key = []
    for _, p in pd.read_csv(args.participants).iterrows():
        pid, user = str(p["participant_id"]), str(p["username"])
        games = fetch_last_n_games(user, n=args.games, time_class=args.time_class)
        result = analyse_games(games, username=user, depth=args.depth, time_class=args.time_class)
        grounded = result["text_report"]
        for card in result["training_plan"]:
            grounded += f"\n\n{metric_label(card['weakness'])}:\n" + "\n".join(
                f"- Game {i['game_number']}, {i['move_label']}: {i['explanation']} ({i['position_url']})"
                for i in card["instances"])
        baseline = baseline_report(pd.DataFrame(result["timeline"]), user)
        order = ["grounded", "baseline"]
        rng.shuffle(order)
        texts = {"grounded": grounded, "baseline": baseline}
        for label, condition in zip("AB", order):
            (out / f"{pid}_report_{label}.txt").write_text(texts[condition])
        key.append({"participant_id": pid, "A": order[0], "B": order[1]})
        print(f"{pid}: done")
    pd.DataFrame(key).to_csv(out / "key.csv", index=False)


if __name__ == "__main__":
    main()
