"""RQ1 step 2: precision and inter-annotator agreement from the filled sheet.

Usage:
    python -m scripts.score_motif_annotations data/evaluation/annotation_sheet.csv
"""

from __future__ import annotations

import sys

import pandas as pd

from src.evaluation.metrics import cohen_kappa


def main() -> None:
    sheet = pd.read_csv(sys.argv[1] if len(sys.argv) > 1 else "data/evaluation/annotation_sheet.csv")
    done = sheet.dropna(subset=["annotator_A", "annotator_B"])
    if done.empty:
        raise SystemExit("No rows have both annotator_A and annotator_B filled in yet.")
    a, b = done["annotator_A"].astype(int).tolist(), done["annotator_B"].astype(int).tolist()
    both = [x and y for x, y in zip(a, b)]
    print(f"rows scored:            {len(done)}")
    print(f"precision (annotator A): {sum(a) / len(a):.3f}")
    print(f"precision (annotator B): {sum(b) / len(b):.3f}")
    print(f"precision (both agree):  {sum(both) / len(both):.3f}")
    print(f"Cohen's kappa:           {cohen_kappa(a, b):.3f}")
    for motif, group in done.groupby("claimed_motif"):
        ga = group["annotator_A"].astype(int)
        print(f"  {motif:7s} n={len(group):3d}  precision(A)={ga.mean():.3f}")


if __name__ == "__main__":
    main()
