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

### 2026-09-18 — Phase 6: Recommendation Engine
**Completed:**
- `src/recommend/recommender.py`: `recommend_for_weakness()` (metric -> training_type,
  Lichess puzzle theme slugs, training links, description) and `build_training_plan()`
  (ranked weakness tags -> list of concrete recommendations, in severity order). Covers all
  weakness-vector metrics: blunder/mistake/inaccuracy/missed_tactic rate -> real Lichess puzzle
  theme links (`fork`, `pin`, `skewer`, `hangingPiece`, `advantage`, `middlegame`, `endgame`,
  `pawnEndgame`, `rookEndgame` — all verified real Lichess training theme slugs, no fabricated
  themes); pawn_weakness_rate and opening_blunder_rate get study-note-style recommendations
  since pawn structure isn't itself a Lichess puzzle theme
- `tests/test_phase6_smoke.py`: verifies a single weakness maps to valid `lichess.org/training/`
  links; verifies a full ranked weakness list (from the same synthetic persistent-weakness
  timeline used in Phases 4-5) produces one recommendation per weakness, every one with a
  non-empty description and either a concrete link or an explicit study-note type

**In progress / broken:**
- None

**Decisions made:**
- Any weakness metric without a curated entry falls back to a generic 'advantage' puzzle
  recommendation rather than returning nothing, so `build_training_plan()` can never silently
  drop a weakness the report named
- `pawn_weakness_rate` is intentionally NOT mapped to a Lichess puzzle theme (no matching real
  theme exists) — mapped to `training_type: 'opening_study'` with a text recommendation instead,
  rather than inventing a nonexistent puzzle theme slug

**Next step:**
- Phase 7: wire `src/main.py` to orchestrate the full pipeline end-to-end (ingestion ->
  annotation -> features -> weakness -> NLP -> recommendation), add basic per-module tests under
  `tests/`, and confirm one command takes a username in and produces a full report + training
  plan out with no manual steps in between

---

### 2026-09-18 — Phase 5: NLP Report Generation
**Completed:**
- `src/weakness/aggregate.py`: added `rank_weakness_tags()` (persistent weaknesses first by
  latest EWM value, then remaining tracked metrics) — the ranked weakness-tag list required by
  Architecture.md §4's NLP->Recommendation contract, computed in the weakness layer (it already
  has the trend data) and forwarded through NLP to Recommendation
- `src/nlp/templates.py`: `move_to_text()` (Phase 5A deterministic per-move sentence),
  `weakness_summary_sentence()`, and `template_report()` — the deterministic baseline report,
  always available with zero external dependencies
- `src/nlp/report_generator.py`: `build_report_prompt()` (grounds the LLM strictly in the
  pipeline's own computed numbers — no invented stats) and `generate_coaching_report()`, which
  calls the Anthropic Messages API directly via `requests` when `ANTHROPIC_API_KEY` is set, and
  falls back to `templates.template_report()` on a missing key or any call failure, always
  returning `{text_report, source}`
- `tests/test_phase5_smoke.py`: verifies `move_to_text()` on a synthetic row; verifies
  `template_report()` produces a real multi-paragraph, coherent report (not just stats) from a
  synthetic 8-game timeline with a genuine persistent blunder-rate weakness; verifies
  `build_report_prompt()` is correctly grounded; verifies `generate_coaching_report()` returns a
  valid multi-paragraph report via its fallback path

**In progress / broken:**
- `ANTHROPIC_API_KEY` is not set in this sandboxed session, so the LLM path
  (`source == 'llm'`) has **not** been exercised against the real API here — only its
  documented fallback (`source == 'template_fallback'`) has been verified. The LLM call code
  itself (`_call_anthropic_api`) is fully implemented against the real Anthropic Messages API
  shape. Recommend setting `ANTHROPIC_API_KEY` and re-running
  `python3 tests/test_phase5_smoke.py` locally to confirm `source == 'llm'` and inspect real
  model output before treating Phase 5B as fully proven end-to-end.

**Decisions made:**
- Used `requests` directly against the Anthropic Messages API rather than adding the
  `anthropic` SDK package as a new dependency, per Rules.md's constraint on introducing new
  NLP/LLM dependencies without justification — `requests` is already a project dependency
- LLM path failure (any exception, including missing API key) always falls back to
  `template_report()` rather than raising — per Rules.md §2 (one external call must never crash
  the pipeline) and Phases.md's own sanctioned cut order (LLM falls back to templates, never to
  nothing)
- The prompt explicitly instructs the model to use only the given data and never invent
  statistics/opening names, keeping the "grounded NLP framework" claim in PRD.md defensible
  even when the LLM path is live

**Next step:**
- Phase 6: implement `src/recommend/recommender.py` (ranked weakness tags -> Lichess puzzle
  themes / opening study / endgame drill suggestions)

---

### 2026-09-18 — Phase 4: Weakness Modeling
**Completed:**
- `src/weakness/vectorize.py`: `build_weakness_vector()` (one game's move rows -> a dict of
  rate-based weakness signals: blunder/mistake/inaccuracy rate, per-phase blunder rate,
  pawn_weakness_rate, king_safety_avg, missed_tactic_rate, plus eco/opening_name) and
  `vectorize_games()` (batch entry point, one row per game)
- `src/weakness/aggregate.py`: `sort_chronologically()` (orders by parsed PGN Date header),
  `add_rolling_trends()` (adds `_rolling` and `_ewm` columns per metric), and
  `identify_persistent_weaknesses()` (flags a metric only if its EWM trend has stayed above
  threshold for every one of the last `min_games` games — the transient-vs-persistent test
  central to PRD.md)
- LSTM stretch (`lstm_model.py`) intentionally not built yet — Phases.md marks it a stretch
  goal, not required for "Done when"; revisit only if time remains after Phase 7
- `tests/test_phase4_smoke.py`: (1) real annotate->feature->vectorize pipeline on a real game,
  confirms vector shape/value ranges; (2) synthetic 8-game chronological timeline with a
  deliberate sustained blunder-rate rise vs. a one-off mistake-rate spike — confirms
  `identify_persistent_weaknesses` flags the sustained rise and correctly does NOT flag the
  transient spike

**In progress / broken:**
- None (LSTM stretch deferred, not broken — see above)

**Decisions made:**
- `missed_tactic_rate` proxy: among positions where a fork/pin/skewer motif was geometrically
  present for the mover, what fraction were played as blunder/mistake — returns 0.0 (not None)
  when no motif-bearing positions occurred in that game
- Trend threshold defaults (judgment calls, documented as constants in aggregate.py):
  rolling window = 5 games, EWM span = 5 games, persistence requires >=3 games with EWM rate
  above 0.15 — chosen so a single bad game never triggers "persistent", but a real sustained
  rise (as in the smoke test) is reliably caught within a handful of games
  EWM is treated as the primary trend signal (used by identify_persistent_weaknesses) since it
  weights recent games more without needing a hard cutoff; rolling mean is kept alongside as a
  simpler, more literal reference series for the report/chart layer

**Next step:**
- Phase 5: implement `src/nlp/templates.py` (deterministic move-to-text templating) and
  `src/nlp/report_generator.py` (LLM-based coaching report from the weakness vector + trend
  data)

---

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
