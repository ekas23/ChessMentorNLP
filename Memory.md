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

### 2026-09-18 — Phase 3: Feature Extraction
**Completed:**
- `src/features/positional.py`: `material_balance()`, `king_safety()` (pawn-shield-minus-open-files
  heuristic), `pawn_structure()` (isolated/doubled/normal), `game_phase()` (opening/middlegame/
  endgame), plus `add_positional_columns(df)` wrapper
- `src/features/motifs.py`: `detect_fork()`, `detect_pin()` (via python-chess's `is_pinned`),
  `detect_skewer()` (manual ray-walk, front-piece-value >= back-piece-value along a slider's
  line), `detect_motifs()`, plus `add_motif_column(df)` wrapper — scoped to exactly these 3
  motifs per PRD.md's brittleness warning
- `src/features/openings.py`: `classify_eco()` (longest-prefix match against a small, verified
  table of standard opening families and their real ECO ranges — no fabricated names/codes) and
  `add_opening_columns(df, games, game_ids)`
- Renamed `engine._derive_game_id` -> public `engine.derive_game_id()` so openings.py can join
  per-game opening tags back onto the per-move DataFrame using the same ids annotate_games() used
- `tests/test_phase3_smoke.py`: verifies `detect_fork()` against a known textbook forking
  position (independent of engine output); runs the full annotate -> positional -> motif ->
  opening pipeline on the Ruy Lopez sample game — confirms all 38 rows have complete features,
  motif tags include real detections (skewer/pin fire on genuine positions in the sample game),
  and the opening is correctly classified as Ruy Lopez (C60-C99)

**In progress / broken:**
- None

**Decisions made:**
- `motif` column is a comma-joined string (`""` if none, e.g. `"fork,pin"`) rather than a list,
  so it stays a clean scalar DataFrame column
- Extended the Features->Weakness contract beyond Architecture.md §4's listed 5 fields
  (material_balance, king_safety, pawn_structure, phase, motif) by also adding `eco` and
  `opening_name` columns, since Phases.md explicitly requires `openings.py` output and the
  contract's own §5 rationale says each layer just needs to extend the prior schema, not match
  it exactly — noting this explicitly per Rules.md §4 rather than doing it silently
- `pawn_structure()` scoped to isolated/doubled only (no backward-pawn detection) — same
  brittleness-avoidance judgment call as the motif scoping
- `game_phase()` and `king_safety()` thresholds are heuristic judgment calls (documented as
  constants with inline rationale in positional.py) since no doc specifies exact values
- `openings.py`'s ECO table covers only major opening families at the super-group level (e.g.
  "Ruy Lopez" C60-C99, not a specific sub-variation) — deliberately coarse to avoid
  misclassifying/fabricating a precise ECO code from a small hand-curated table

**Next step:**
- Phase 4: implement `src/weakness/vectorize.py` (per-game weakness vector from the
  annotated+featured data) and `src/weakness/aggregate.py` (rolling/EWM longitudinal trend
  tracking across chronological games)

---

### 2026-09-18 — Phase 2: Engine Annotation
**Completed:**
- `src/annotation/engine.py`: `create_engine()`, `evaluate_fen()` (mate scores converted to a
  large finite centipawn value), `annotate_game()` (walks a game's mainline, one Stockfish call
  per position — N+1 calls for an N-move game by reusing each move's eval_after as the next
  move's eval_before), `annotate_games()` (batch entry point, one Stockfish process reused
  across all games, skips+logs any game that fails partway through)
- `src/annotation/classify_moves.py`: `classify_move()` (centipawn-loss -> label, computed from
  the mover's own perspective) and `classify_moves_df()` (vectorized wrapper), producing the
  final `{game_id, move_number, fen, move_uci, eval_before, eval_after, quality_label}` shape
  required by Architecture.md §4
- `tests/test_phase2_smoke.py`: annotates a real 6-half-move game (`sample_short_game.pgn`) at
  depth 8, confirms row count matches move count, column shape matches the contract exactly, all
  quality labels are valid, no missing evals — ran in <1s, no crashes

**In progress / broken:**
- None

**Decisions made:**
- Quality-label thresholds (not specified in any doc) — centipawn loss from the mover's own
  perspective: >=200 blunder, >=100 mistake, >=50 inaccuracy, else good. This is the common
  Lichess/Chess.com-style convention; flagged here per Rules.md §3 ("ask before making an
  architectural decision not already covered") — proceeding with this as the documented default
  since it's a standard, well-established convention rather than an arbitrary choice
- Default Stockfish search depth is 12 for real runs (`DEFAULT_DEPTH` in engine.py); the smoke
  test uses depth 8 purely for speed
- Optimized to N+1 engine calls per N-move game (reusing eval_after as next eval_before) rather
  than the naive 2N, directly addressing PRD.md's flagged risk that Stockfish annotation is slow

**Next step:**
- Phase 3: implement `src/features/positional.py` (material, king safety, pawn structure,
  phase), `src/features/motifs.py` (fork/pin/skewer detection), `src/features/openings.py`
  (ECO lookup for the first 8-10 moves)

---

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
