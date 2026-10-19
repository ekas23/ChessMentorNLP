# Evaluation protocol (for the paper)

The paper's Section VI defines four research questions. This file says exactly how to
produce each number in Table III. **Never fill the paper with numbers that did not come
out of these steps.** The synthetic games in `data/raw_pgn/synthetic_games.pgn` are for
tests only and must not be reported as results.

Everything below runs on your laptop (it needs internet access to Chess.com and a local
Stockfish). Install first:

```bash
pip install -r requirements.txt -r requirements-eval.txt
```

Use **one time control** for all evaluation runs (rapid is recommended) and the default
depth (14). Report both in the paper.

---

## RQ3 — Cohort behaviour (run this first; RQ1 and RQ2 reuse its output)

1. Make `docs/cohort_accounts.csv` with columns `username,band` — about 30 public
   Chess.com accounts that play rapid regularly, spread across rating bands
   (`<1200`, `1200-1600`, `1600-2000`, `>2000`). Classmates, club members and your own
   accounts are fine; ask permission if you name anyone in the paper (better: don't name them).
2. Run:
   ```bash
   python -m scripts.run_cohort --accounts docs/cohort_accounts.csv --games 50 --time-class rapid
   ```
   Expect roughly 3–8 minutes per account on a laptop the first time (results are cached).
3. Output: `data/evaluation/cohort/cohort_summary.csv`. For the paper, report per rating
   band: mean blunder / mistake / missed-tactic rate, and how many accounts got each flag.
   The expectation is that rates fall as rating rises; if they don't, say so honestly.

## RQ2 — Persistence stability

Already computed by `run_cohort`: columns `split_agreement` and `split_jaccard` in
`cohort_summary.csv` (flags computed separately on games 1–25 and 26–50).
Report the mean and spread across accounts.

## RQ1 — Motif-detection precision (needs two people)

1. ```bash
   python -m scripts.export_motif_sample --cohort data/evaluation/cohort --n 100
   ```
   This writes `data/evaluation/annotation_sheet.csv`.
2. Give the sheet to two chess players (1600+ if possible) — they must work **independently**.
   For each row they open `position_link`, check whether `claim` is a real, working tactic in
   that position, and enter `1` (valid) or `0` (not valid) in their own column
   (`annotator_A` / `annotator_B`).
3. ```bash
   python -m scripts.score_motif_annotations data/evaluation/annotation_sheet.csv
   ```
   Report precision (per annotator and where both agree) and Cohen's kappa.

## RQ4 — Perceived usefulness (user study, needs 15–20 players)

1. Make `participants.csv` with `participant_id,username` (use IDs like P01, never names in the paper).
2. ```bash
   python -m scripts.make_study_reports --participants participants.csv --time-class rapid
   ```
   Each participant gets `P01_report_A.txt` and `P01_report_B.txt`: one is the grounded
   report, the other the statistics-only baseline, in random order. `key.csv` holds the
   mapping — do not show it to participants.
3. Each participant reads both reports and answers the form below once per report.
4. Collect answers in `responses.csv` with columns
   `participant_id,report,accuracy,specificity,actionability` (report = A or B).
5. ```bash
   python -m scripts.analyse_study data/evaluation/study/responses.csv data/evaluation/study/key.csv
   ```
   Report medians per condition and the Wilcoxon signed-rank p-values.

### Questionnaire (5-point scale: 1 = strongly disagree, 5 = strongly agree)

Ask these three statements for **each** report:

1. **Accuracy** — "This report describes my real weaknesses correctly."
2. **Specificity** — "This report points to concrete things in my own games."
3. **Actionability** — "After reading this report I know what to practise."

Optional free-text question: "What, if anything, was wrong or missing in this report?"

Get informed consent: tell participants what data is used (their public Chess.com games),
that participation is voluntary, and that results are reported anonymously.
