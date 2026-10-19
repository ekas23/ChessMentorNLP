# ChessMentorNLP

Enter a Chess.com username and get a coaching report built around **recurring**
weaknesses: every move is checked by Stockfish, a weakness is only flagged when it keeps
coming back across your games, and each one is shown with concrete moves from your own
games plus matching practice.

## Setup (Windows, macOS, Linux)

1. Python 3.10+.
2. Stockfish: download it from <https://stockfishchess.org/download/>, unzip, and either
   put the folder on your PATH or point to the program directly, e.g. in PowerShell:
   ```powershell
   $env:STOCKFISH_PATH = "C:\Tools\stockfish\stockfish-windows-x86-64-avx2.exe"
   ```
3. Install the Python packages (a virtual environment is recommended):
   ```bash
   python -m venv .venv
   .venv\Scripts\activate        # Windows  (macOS/Linux: source .venv/bin/activate)
   pip install -r requirements.txt
   ```

## Run

Dashboard (opens at <http://127.0.0.1:5000>):
```bash
python -m src.webapp.app
```

Command line:
```bash
python -m src.main --username YOUR_NAME --max-games 50 --time-class rapid
```

The first run on 50 games takes a few minutes (each move is analysed at depth 14);
results are cached in `data/annotated/cache/`, so re-runs are fast.

Optional: set `ANTHROPIC_API_KEY` to have the narrative written by an LLM from the
computed results; without it a deterministic template is used.

## Tests

```bash
pytest
```
Engine tests are skipped automatically if Stockfish isn't installed.

## How it works

| Stage | What it does |
|---|---|
| Ingestion | Chess.com public API, last N games, optional time-control filter, variants skipped |
| Annotation | Stockfish via `python-chess`; scores read from White's view; mates capped at ±1000 |
| Move labels | Lichess's winning-chance method: drop ≥ 0.3 blunder, ≥ 0.2 mistake, ≥ 0.1 inaccuracy |
| Features | Phase, king safety, pawn weaknesses **created** by a move, fork/pin/skewer created by the engine's best move |
| Weakness vectors | Per game, over **the analysed player's moves only**; games under 10 moves excluded |
| Persistence | EWMA (span 10) above a per-metric threshold, present in ≥ 30% of games, and in both halves of the history |
| Report | Examples per recurring weakness with game, full-move number, opponent, winning-chance change and a link to the position |

Evaluation for the paper: see [docs/EVALUATION.md](docs/EVALUATION.md).
Change history and design decisions: see [Memory.md](Memory.md).
