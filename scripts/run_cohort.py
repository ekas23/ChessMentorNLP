"""RQ2 + RQ3: run the pipeline over a cohort of public Chess.com accounts.

Input: a CSV with columns `username,band` (band = rating band label, e.g. 1200-1600).
For every account it fetches the last N games of ONE time class, analyses them, and
writes to --out:
    <username>/moves.csv     every annotated move (input to export_motif_sample.py)
    <username>/games.csv     per-game weakness vectors
    <username>/result.json   persistence diagnostics, flags, split-half result
    cohort_summary.csv       one row per account (for Table III of the paper)

Needs internet access to Chess.com and a local Stockfish. Annotations are cached, so
an interrupted run can simply be restarted.

Usage:
    python -m scripts.run_cohort --accounts docs/cohort_accounts.csv --games 50 --time-class rapid
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from pathlib import Path

import pandas as pd

from src.evaluation.metrics import split_half_agreement
from src.ingestion.fetch_games import fetch_last_n_games
from src.main import analyse_games
from src.weakness.aggregate import TREND_METRICS

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("cohort")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--accounts", required=True, help="CSV with columns username,band")
    ap.add_argument("--games", type=int, default=50)
    ap.add_argument("--time-class", default="rapid", choices=["bullet", "blitz", "rapid", "daily"])
    ap.add_argument("--depth", type=int, default=14)
    ap.add_argument("--out", default="data/evaluation/cohort")
    args = ap.parse_args()

    accounts = pd.read_csv(args.accounts)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    summary = []
    for _, acc in accounts.iterrows():
        user, band = str(acc["username"]).strip(), acc.get("band", "")
        log.info("== %s (%s)", user, band)
        started = time.time()
        try:
            games = fetch_last_n_games(user, n=args.games, time_class=args.time_class)
            result = analyse_games(games, username=user, depth=args.depth, requested_n=args.games,
                                   time_class=args.time_class, return_moves=True)
        except Exception as exc:  # noqa: BLE001 -- one bad account must not stop the cohort
            log.warning("skipping %s: %s", user, exc)
            summary.append({"username": user, "band": band, "error": str(exc)})
            continue
        user_dir = out / user
        user_dir.mkdir(exist_ok=True)
        result["moves"].to_csv(user_dir / "moves.csv", index=False)
        games_df = pd.DataFrame(result["timeline"])
        games_df.to_csv(user_dir / "games.csv", index=False)
        split = split_half_agreement(games_df)
        (user_dir / "result.json").write_text(json.dumps({
            "username": user, "band": band, "persistent": result["persistent_weaknesses"],
            "diagnostics": result["diagnostics"], "split_half": split,
            "games_analyzed": result["games_analyzed"], "games_skipped": result["games_skipped"],
        }, indent=2))
        row = {"username": user, "band": band, "games": result["games_analyzed"],
               "n_persistent": len(result["persistent_weaknesses"]),
               "split_agreement": split["agreement"], "split_jaccard": split["jaccard"],
               "seconds": round(time.time() - started)}
        for m in TREND_METRICS:
            d = result["diagnostics"].get(m, {})
            row[f"{m}_ewm"] = d.get("ewm")
            row[f"{m}_persistent"] = d.get("persistent")
        summary.append(row)
        pd.DataFrame(summary).to_csv(out / "cohort_summary.csv", index=False)
    log.info("done -> %s", out / "cohort_summary.csv")


if __name__ == "__main__":
    main()
