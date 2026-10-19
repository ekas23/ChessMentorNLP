"""RQ4 step 2: compare ratings of the grounded report vs the baseline.

Input: responses.csv with columns participant_id,report,accuracy,specificity,actionability
(report = A or B as the participant saw it; ratings 1-5), plus key.csv from
make_study_reports.py. Output: medians per condition and a Wilcoxon signed-rank
test per question. Needs scipy (pip install scipy).

Usage:
    python -m scripts.analyse_study data/evaluation/study/responses.csv data/evaluation/study/key.csv
"""

from __future__ import annotations

import sys

import pandas as pd

QUESTIONS = ["accuracy", "specificity", "actionability"]


def main() -> None:
    from scipy.stats import wilcoxon

    responses = pd.read_csv(sys.argv[1])
    key = pd.read_csv(sys.argv[2]).astype({"participant_id": str})
    responses["participant_id"] = responses["participant_id"].astype(str)
    long = responses.merge(key, on="participant_id")
    long["condition"] = [row[row["report"]] for _, row in long.iterrows()]
    wide = long.pivot(index="participant_id", columns="condition", values=QUESTIONS)
    print(f"participants: {len(wide)}")
    for q in QUESTIONS:
        g, b = wide[(q, "grounded")], wide[(q, "baseline")]
        stat = wilcoxon(g, b, zero_method="wilcox") if (g != b).any() else None
        p = f"p = {stat.pvalue:.4f}" if stat else "no differences"
        print(f"{q:14s} median grounded = {g.median():.1f}, baseline = {b.median():.1f}, Wilcoxon {p}")


if __name__ == "__main__":
    main()
