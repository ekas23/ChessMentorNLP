"""RQ1 step 1: sample detected missed tactics for two human annotators.

Reads every <username>/moves.csv written by run_cohort.py, keeps the analysed
players' missed tactics, draws a random sample, and writes a spreadsheet where
each annotator marks whether the claimed tactic is real (1) or not (0).

Usage:
    python -m scripts.export_motif_sample --cohort data/evaluation/cohort --n 100
Then give annotation_sheet.csv to two chess players (1600+ recommended). They fill
the annotator_A / annotator_B columns independently, without discussing.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from src.nlp.instances import LICHESS_ANALYSIS_URL


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cohort", default="data/evaluation/cohort")
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--out", default="data/evaluation/annotation_sheet.csv")
    args = ap.parse_args()

    frames = []
    for path in Path(args.cohort).glob("*/moves.csv"):
        df = pd.read_csv(path, keep_default_na=False, na_values=[""])
        df = df[(df["is_player"].astype(str) == "True") & (df["missed_tactic"].astype(str) == "True")]
        df["username"] = path.parent.name
        frames.append(df)
    if not frames:
        raise SystemExit("No missed tactics found -- run scripts.run_cohort first.")
    pool = pd.concat(frames, ignore_index=True)
    sample = pool.sample(n=min(args.n, len(pool)), random_state=args.seed).reset_index(drop=True)
    sheet = pd.DataFrame({
        "id": range(1, len(sample) + 1),
        "username": sample["username"],
        "move": [f"{int(r.move_number)}{'.' if r.side == 'white' else '...'} {r.move_san}" for r in sample.itertuples()],
        "position_link": [LICHESS_ANALYSIS_URL.format(fen=f.replace(" ", "_"), color=s)
                          for f, s in zip(sample["fen"], sample["side"])],
        "claimed_motif": sample["motif"],
        "claim": sample["motif_detail"],
        "move_played": sample["move_san"],
        "annotator_A": "",
        "annotator_B": "",
        "notes": "",
    })
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    sheet.to_csv(args.out, index=False)
    print(f"{len(sheet)} rows (from a pool of {len(pool)}) -> {args.out}")


if __name__ == "__main__":
    main()
