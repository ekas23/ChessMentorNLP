# ChessMentorNLP — Architecture

## 1. High-Level Flow

```
Game Source (Chess.com username + number of games, default 50 — single input,
             no PGN upload, no source selection; see Memory.md 2026-09-21)
        │
        ▼
[1] Ingestion Layer  ──► fetch_last_n_games(username, n) → parsed game objects
        │
        ▼
[2] Annotation Layer ──► Stockfish eval per move → move quality labels
        │
        ▼
[3] Feature Layer    ──► positional features + tactical motif tags per position
        │
        ▼
[4] Weakness Layer   ──► per-game weakness vector → longitudinal aggregation (EWM / LSTM)
        │
        ▼
[5] NLP Layer        ──► move-to-text templates + LLM-based coaching report generation
        │
        ▼
[6] Recommendation   ──► weakness tags → puzzle/opening/endgame drill suggestions
        │
        ▼
   Output: Coaching Report + Training Plan (CLI / notebook / simple web view)
```

## 2. Technical Stack

| Layer | Tool/Library |
|---|---|
| Language | Python 3.10+ |
| Chess parsing | `python-chess` |
| Engine | Stockfish (binary, via `stockfish` pip wrapper) |
| Data handling | `pandas`, `numpy` |
| Sequence modeling (stretch) | `torch` (LSTM) |
| NLP report generation | Template strings (baseline) → LLM API call (upgrade) |
| API access | `requests` (Chess.com public API — primary; Lichess code retained but deprioritized, see Memory.md 2026-09-21) |
| Storage | Local CSV/Parquet files or SQLite (no need for a full DB) |
| Interface | Jupyter notebook, a minimal CLI (`argparse`), and a local-only Flask dashboard (explicit user request, deviates from the default no-web-framework rule — see Memory.md) |

## 3. Folder Structure

```
chessmentor_nlp/
├── data/
│   ├── raw_pgn/                # local PGN fixtures used only by the test suite
│   │                           # (offline testing; NOT a product upload path)
│   ├── annotated/              # per-move engine annotations (CSV/parquet)
│   └── weakness_vectors/       # per-game weakness vectors, timeline data
│
├── src/
│   ├── ingestion/
│   │   ├── fetch_games.py      # fetch_last_n_games(username, n=50) -> list[Game] is the
│   │   │                       # single product-facing entry point (Chess.com only, no
│   │   │                       # manual PGN upload, no source selection — see Memory.md
│   │   │                       # 2026-09-21). Lichess helpers retained but not wired in.
│   │   └── parse_pgn.py        # PGN string/file -> game objects (parse_pgn_string is used
│   │                           # by fetch_last_n_games; parse_pgn_file is a lower-level
│   │                           # utility kept for the test suite's offline fixtures, not
│   │                           # a user-facing upload feature)
│   │
│   ├── annotation/
│   │   ├── engine.py           # Stockfish wrapper, eval per move
│   │   └── classify_moves.py   # blunder/mistake/inaccuracy labeling
│   │
│   ├── features/
│   │   ├── positional.py       # material, king safety, pawn structure, phase
│   │   ├── motifs.py           # fork/pin/skewer detection
│   │   └── openings.py         # ECO classification
│   │
│   ├── weakness/
│   │   ├── vectorize.py        # per-game weakness vector construction
│   │   ├── aggregate.py        # rolling/EWM longitudinal tracking
│   │   └── lstm_model.py       # (stretch) sequence model for trend prediction
│   │
│   ├── nlp/
│   │   ├── templates.py        # move-to-text templating
│   │   └── report_generator.py # LLM-based coaching report generation
│   │
│   ├── recommend/
│   │   └── recommender.py      # weakness tag → puzzle/training mapping
│   │
│   ├── webapp/                 # local-only Flask dashboard (explicit user request,
│   │   ├── app.py              # deviates from the default no-web-framework rule --
│   │   ├── templates/          # see Rules.md and Memory.md for why; reuses
│   │   └── static/             # main.run_pipeline() rather than duplicating logic)
│   │
│   └── main.py                 # orchestrates the full pipeline end-to-end
│
├── notebooks/
│   └── exploration.ipynb       # ad-hoc analysis, debugging, visualizations
│
├── tests/
│   └── ...                     # unit tests per module
│
├── PRD.md
├── Architecture.md
├── Rules.md
├── Phases.md
├── Design.md
├── Memory.md
└── requirements.txt
```

## 4. Data Contracts (what flows between layers)

- **Ingestion → Annotation**: list of `chess.pgn.Game` objects
- **Annotation → Features**: DataFrame, one row per move — `{game_id, move_number, fen, move_uci, eval_before, eval_after, quality_label}`
- **Features → Weakness**: same DataFrame, extended with `{material_balance, king_safety, pawn_structure, phase, motif}`
- **Weakness → NLP**: DataFrame, one row per game — the weakness vector, plus a rolling/trend column
- **NLP → Recommendation**: list of weakness tags ranked by severity/persistence
- **Recommendation → Output**: final report object — `{text_report, training_plan}`

## 5. Why this structure
Each layer only depends on the output schema of the layer before it, not its internals —
so you can swap Stockfish for another engine, or swap the template-based report generator
for an LLM-based one, without touching the rest of the pipeline. This also maps cleanly onto
Phases.md: each phase in the build order corresponds to finishing one layer's contract before
moving to the next.
