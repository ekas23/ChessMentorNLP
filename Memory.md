# ChessMentorNLP — Memory.md

This file is not filled in at project start. Begin updating it once coding actually begins,
after each meaningful chunk of work (end of a session, end of a phase, or a significant
decision). Its purpose is to let you (or an AI assistant in a fresh chat/tool) pick up exactly
where you left off without re-reading the whole codebase or re-deriving decisions already made.

Keep entries short and factual. Newest entry at the top.

---

## How to use this file
- After finishing work: add a dated entry below with (a) what was completed, (b) what's
  currently in progress/broken, (c) what decision comes next
- Before starting a new session: read the top entry first, then Phases.md, before touching code
- If a design/architecture decision is made that deviates from PRD.md/Architecture.md/Rules.md,
  note it here AND update the relevant doc — this file is a log, not the source of truth for
  current state

---

## Template for a new entry

```
### YYYY-MM-DD — Phase X: <short title>
**Completed:**
-

**In progress / broken:**
-

**Decisions made:**
-

**Next step:**
-
```

---

## Log

### 2026-09-18 — Phase 0: Environment Setup
**Completed:**
- Created the full folder structure from Architecture.md §3 (`data/{raw_pgn,annotated,weakness_vectors}`,
  `src/{ingestion,annotation,features,weakness,nlp,recommend}` each with `__init__.py`, `notebooks/`, `tests/`)
- Copied the six project docs (PRD/Architecture/Rules/Phases/Design/Memory) into the repo root
- Added `requirements.txt` (python-chess, stockfish, pandas, numpy, requests) and `.gitignore`
- Installed the Stockfish binary via `apt-get install stockfish` (lands at `/usr/games/stockfish`,
  not on PATH by default) and created a project-local `.venv` with all Python deps (system pip
  failed building the `chess` wheel due to a broken setuptools `install_layout` issue in this
  environment — a clean venv avoided it)
- Added `src/config.py` with `resolve_stockfish_path()` (PATH lookup + fallback to known install
  locations) and shared data-dir path constants, plus a sample PGN at `data/raw_pgn/sample_game.pgn`
- Wrote `tests/test_phase0_smoke.py`: loads the sample PGN with `python-chess` and evaluates the
  starting position with Stockfish — ran successfully (`{'type': 'cp', 'value': 50}`)

**In progress / broken:**
- None

**Decisions made:**
- Use a project-local `.venv` (not system pip) — system pip's setuptools install fails on this
  environment for source-built wheels (`chess` package); venv install is clean and reproducible
- Added `src/config.py` as shared cross-cutting infra (path constants, Stockfish binary resolution)
  even though it isn't one of the named layer files in Architecture.md §3 — it's not a pipeline
  layer itself, just config used by multiple layers (mainly `annotation/engine.py` later)

**Next step:**
- Phase 1: implement `src/ingestion/fetch_games.py` (Chess.com/Lichess API pull) and
  `src/ingestion/parse_pgn.py` (PGN → game objects), supporting both API pull by username and
  manual PGN upload
