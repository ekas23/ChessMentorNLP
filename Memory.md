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

### 2026-09-18 — Phase 1: Data Ingestion
**Completed:**
- `src/ingestion/parse_pgn.py`: `parse_pgn_string()` and `parse_pgn_file()`, both returning
  `list[chess.pgn.Game]`. Validates each parsed game has at least one move (`_is_well_formed`);
  malformed/empty games are logged and skipped, never halting the batch (per Rules.md §2)
- `src/ingestion/fetch_games.py`: `fetch_chess_com_games()`, `fetch_lichess_games()`, and a
  unified `fetch_games(username, source, max_games)` dispatcher. Chess.com path walks the
  archive-list API newest-first; Lichess path uses the `max` query param on the user-games
  endpoint. Every `requests` call is wrapped in try/except, logs a clear error, and returns
  `[]` on failure rather than raising into the pipeline (per Rules.md §2)
- `tests/test_phase1_smoke.py`: 4 checks, all passing — PGN-file parsing against a real
  3-game fixture (`data/raw_pgn/sample_multi_game.pgn`, one deliberately empty game to confirm
  skip-and-log), PGN-string parsing, and both API-fetch functions against mocked HTTP responses

**In progress / broken:**
- Live API calls to `api.chess.com` and `lichess.org` could not be verified in this sandboxed
  session — its egress proxy returns 403 for both hosts (confirmed via direct `requests.get`
  attempts). `fetch_chess_com_games`/`fetch_lichess_games` are implemented against each API's
  real, documented response shape and verified via mocked `requests.get` responses, but have
  **not** been exercised against the live APIs. Recommend running
  `python3 -c "from src.ingestion.fetch_games import fetch_games; print(len(fetch_games('<your_username>', source='chess.com', max_games=5)))"`
  locally (outside this sandbox) to confirm before relying on it for Phase 2+.

**Decisions made:**
- Chess.com archive walk stops as soon as `max_games` is reached, iterating archive months
  newest-first then games within a month newest-first — avoids downloading a player's entire
  history when only recent games are needed
- A failed *individual* archive-month fetch is logged and skipped (partial results returned);
  a failed *archive-list* fetch (the first call) returns `[]` for the whole pull, since there's
  nothing to iterate without it

**Next step:**
- Phase 2: implement `src/annotation/engine.py` (Stockfish eval per move, before/after) and
  `src/annotation/classify_moves.py` (eval swing → blunder/mistake/inaccuracy/good), producing
  the per-move DataFrame per Architecture.md §4 (`{game_id, move_number, fen, move_uci,
  eval_before, eval_after, quality_label}`)

---

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
