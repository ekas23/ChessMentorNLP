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

### 2026-09-22 — Phase 5/6 Enhancement: Personalized Training Plan with Game Examples
**Completed:**
- **Data-model check (done first, per the change request's explicit instruction):** the
  per-move annotated DataFrame already retains `fen` (position before the move) and
  `move_uci` (the move actually played) from Phase 2, and `motif`/`pawn_structure`/`phase`
  from Phase 3 — enough to derive a real SAN move string and a real centipawn swing for
  narration. What it did NOT retain was *which* square/piece a detected motif applies to:
  `detect_fork`/`detect_pin`/`detect_skewer` returned booleans only, so a sentence like "a
  fork on f5" could not have been written truthfully from existing data. Flagging this
  explicitly (as instructed) rather than fabricating it: fixed with a small, additive Phase 3
  extension — `features/motifs.py` gained `_fork_detail()`/`_pin_detail()`/`_skewer_detail()`
  (shared by the existing boolean detectors, so detection and detail can never disagree) and
  `describe_motifs()`, producing a real plain-language clause (e.g. "a knight fork on f5
  attacking the opponent's queen and rook") derived purely from the same FEN already stored —
  no new data collection, no new Stockfish calls, no external API. New `motif_detail` column
  added via `add_motif_column()` (additive, existing `motif` column unchanged)
- `annotation/classify_moves.py`: extracted `mover_loss_cp()` from `classify_move()` (same
  calculation, now reusable) so instance narration and move classification share one
  centipawn-swing calculation rather than risking two that drift apart
- New `src/nlp/instances.py`: `filter_moves_for_metric()` (mirrors vectorize.py's exact
  per-metric definitions, so an "instance" always genuinely contributes to the stat being
  shown), `select_instances()` (picks up to 4, preferring motif-detail-bearing and
  blunder-sized rows as "clearest to explain" per the request, one per distinct game in a
  first pass so 4 examples means 4 different games, not one bad game), and
  `build_instances_by_weakness()` (the entry point — only builds instances for weaknesses
  already in the `persistent_weaknesses` list passed in; does NOT recompute persistence)
- `recommend/recommender.py`: `match_puzzle_for_instance()` — matches a specific instance's
  own motif tag to a real Lichess theme (fork-miss -> fork puzzles) rather than only the
  weakness category; falls back to blunder/phase/generic themes when no motif is present,
  silently (no UI caveat), per the request. `pawn_weakness_rate` instances get no puzzle link
  (same reasoning as the existing category-level decision: no real Lichess theme covers pawn
  structure). `build_training_plan()`'s first parameter is now explicitly
  `persistent_weaknesses` (not the full ranked list) — a card is only built for a persistent
  weakness, per the request's explicit "do not generate a card for every weakness category."
  Each card gained an `instances` list, each instance carrying its own `puzzle_links`
- `nlp/templates.py` (`template_report`) and `nlp/report_generator.py` (`build_report_prompt`,
  `generate_coaching_report`) extended with an optional `instances_by_weakness` parameter so
  the narrative — template fallback AND the LLM prompt — references concrete games/moves
  ("in Game 12, move 18...") instead of only aggregate rates, satisfying the request's
  "extend its input... so the generated narrative can reference them concretely." The LLM
  prompt explicitly lists the real instances as data and instructs the model to reference at
  least one by game/move number, never to invent additional ones
- `main.py`: wired `build_instances_by_weakness(moves_df, trend_df, persistent)` in after
  trend computation, passed into both `generate_coaching_report()` and `build_training_plan()`
  (which now receives `persistent`, not `ranked_tags`). CLI (`_print_result`) and the webapp
  (`report.html`) both updated to render the required structure: weakness name + persistent
  badge, summary sentence, "Recurring instances:" list with game/move number, explanation, and
  a "Similar puzzle" link per instance
- Tests: new `tests/test_instances.py` (11 tests — filtering, spread-across-games, capping at
  4, motif-detail preference, SAN rendering, centipawn-swing wording), new motif-detail tests
  in `test_features.py` (fork/pin/skewer wording, including a regression test that target
  pieces are correctly attributed to "the opponent's", not "your own" — caught and fixed a
  real wording bug during development), new `match_puzzle_for_instance`/persistent-only tests
  in `test_recommend.py`, new instance-aware tests in `test_nlp.py`, and a full end-to-end
  integration test in `test_main.py` using a real game repeated 3x (to guarantee a genuine
  persistent pattern) confirming the whole chain produces instance-backed cards with working
  puzzle links. All 97 tests passing (up from 69)

**In progress / broken:**
- None

**Decisions made:**
- Fixed the fork/pin/skewer target-piece wording bug caught while testing: `describe_motifs()`
  initially said "your rook and your king" for fork targets, but motif detection runs from the
  mover's own perspective, so targets belong to the *opponent* — corrected to "the opponent's
  rook and king" before this shipped, per Rules.md's ban on fabricating/misattributing chess facts
- `select_instances()`'s "clear and explainable" preference is a 3-tier heuristic (motif-detail
  present > blunder-sized loss with no motif > mistake/inaccuracy with no motif), a judgment
  call since the request didn't specify an exact scoring method — documented here rather than
  left implicit
- Kept `template_report()`/`build_report_prompt()`/`generate_coaching_report()` backward
  compatible (`instances_by_weakness` defaults to `None`) rather than making it required,
  since existing callers/tests without instance data should still produce a valid report
- No "view all N instances" link was added (per the request's own fallback instruction) since
  no such detail-view surface exists in this project — capped at 4 silently

**Next step:**
- None outstanding for this change; ready for the user to try locally against a real,
  multi-game Chess.com history to see genuinely distinct (non-duplicated) example instances

---

### 2026-09-21 — Deliberate Scope Change: Remove PGN Upload, Single-Input Ingestion
**Completed:**
- Removed the PGN-upload input path entirely from the product surface (CLI and web
  dashboard). The ingestion/CLI/dashboard input model is now exactly: Chess.com username
  (str) + number of games to analyze (int, default 50). No file upload, no file-picker UI,
  no "source" selection (Chess.com only for now)
- `src/ingestion/fetch_games.py`: added `fetch_last_n_games(username: str, n: int = 50) ->
  list[chess.pgn.Game]` as the new single ingestion entry point. Walks the player's monthly
  archive list newest-to-oldest, pulling whole months until >= n games collected (or
  archives exhausted), then trims to exactly the most recent n, sorted chronologically
  oldest->newest. Added `_get_with_retry()` (shared GET-with-one-retry helper, real
  `User-Agent` header, no auth) and three specific exceptions:
  `ChessComUsernameNotFoundError` (404 from the archives endpoint), `ChessComNoPublicGamesError`
  (archives list came back empty — private/empty profile), `ChessComAPIError` (any request
  that still fails after one retry)
- `src/main.py`: `run_pipeline()` signature simplified to `(username, max_games=50, depth=...)`
  — no `pgn_file`/`source` parameters. Internals factored into a new
  `_run_pipeline_on_games(games, player_name, depth, requested_n)` so the
  annotate->feature->weakness->nlp->recommend chain stays independently testable against
  local PGN fixtures (used only by the test suite — see below) without needing live network,
  while the product-facing `run_pipeline()` always goes through `fetch_last_n_games`. CLI
  (`main()`) now takes only `--username` (required), `--max-games` (default 50), `--depth`
  — no `--pgn-file`, no `--source`. The result dict gained a `games_requested` field so the
  "fewer than N games available" case can be surfaced clearly ("Analyzed 23 games — this
  account has fewer than 50 total") instead of erroring
- `src/webapp/app.py` + `templates/index.html`: replaced the file-upload form entirely with
  a username + game-count form (no file field, no depth field — dashboard depth is now a
  fixed internal constant, not user-configurable, since the change request said "no other
  fields"). `/analyze` now catches all three new Chess.com exceptions and shows a specific,
  clear message for each (unknown username / private-empty profile / API failure), per
  Rules.md §2. `report.html` shows the "fewer games available than requested" note when
  applicable
- Updated `PRD.md` (Core Features table + Goals) and `Architecture.md` (flow diagram, tech
  stack, folder structure comments) per the change request's explicit instruction to update
  docs before implementing
- Updated the full test suite for the new signatures: `tests/test_ingestion.py` gained 6 new
  tests for `fetch_last_n_games` (correct n-selection + chronological order, fewer-than-n,
  username-not-found, empty-archives, retry-then-succeed, retry-then-fail); `tests/test_main.py`
  and `tests/test_webapp.py` rewritten around the username+n model with mocked Chess.com
  responses. All 55 tests passing (up from 51)

**In progress / broken:**
- None. The live Chess.com path is still only verified via mocked HTTP responses in this
  sandbox (network to api.chess.com is blocked here, as noted since Phase 1) — recommend
  running `python -m src.main --username <your_handle> --max-games 50` locally to confirm
  the real API behavior (especially the 404-on-unknown-username assumption, which is based
  on Chess.com's documented behavior but not verified against a live call from this session)

**Decisions made:**
- **`parse_pgn_file()` was NOT deleted**, despite the change request saying "parse_pgn.py now
  only needs to parse PGN strings returned by the API, not handle file uploads." Read literally
  that would mean deleting the function; instead I kept it as a lower-level utility (still in
  `parse_pgn.py`, still fully general-purpose) used exclusively by the test suite to build game
  lists from local fixtures for offline testing — this sandbox has no live network access to
  Chess.com, so without it almost none of Phases 2-7's pipeline logic could be exercised at all
  in this session. What WAS removed completely, per the literal and clearly primary intent of
  the request, is every *product-facing* entry point that let a user supply a PGN directly:
  the CLI's `--pgn-file` flag and the web dashboard's file-upload form/route are both gone,
  not hidden or deprecated. Flagging this interpretation explicitly per Rules.md §3 rather than
  silently either deleting a function load-bearing for testability or silently keeping a
  product feature the change request asked to remove
- Kept `fetch_chess_com_games()`/`fetch_lichess_games()`/`fetch_games()` (the older, more
  permissive helpers built in Phase 1) unchanged and un-deleted, per the change request's
  explicit instruction not to delete Lichess-related code. They're no longer used by the
  product's main path (`run_pipeline` calls `fetch_last_n_games` directly) but remain
  available for future Lichess work
- Dashboard's Stockfish depth is no longer a user-facing field (previously was) — fixed at a
  constant (10) internally, to strictly honor "no other fields" in the change request. The CLI
  keeps `--depth` as a power-user flag, since that request's "no other fields" language was
  specifically about the *ingestion* input model (username + game count), not analysis tuning
- `_get_with_retry()`'s one retry uses a 1-second sleep between attempts — a small, undocumented
  judgment call (not specified in the change request) to avoid hammering the API immediately
  on a transient failure, without meaningfully slowing down the common case
- Time-control filtering was explicitly NOT built (per the change request's scope note) — all
  games regardless of time control (bullet/blitz/rapid/daily) are pulled and analyzed together.
  **Known limitation to revisit later:** mixed time controls likely skew blunder-rate weakness
  vectors, since blunder rates in 1-minute bullet games are structurally much higher than in
  daily/correspondence games for the same player, and mixing them into one weakness timeline
  could misrepresent a time-control artifact as a genuine chess weakness

**Next step:**
- Verify the live Chess.com path locally (real username, real 404 behavior)
- If/when time-control filtering is picked up later: it would most naturally live as an
  optional filter param on `fetch_last_n_games()` and a new field on the weakness vector
  (Architecture.md §4), not a new pipeline layer

---

### 2026-09-21 — Post-Phase-7: Local Web Dashboard (explicit user request, deviates from Rules.md)
**Completed:**
- `src/webapp/app.py`: a Flask app with two routes — `GET /` (upload form) and
  `POST /analyze` (accepts an uploaded PGN, saves it to a temp file, calls
  `main.run_pipeline(pgn_file=..., username=player_name, depth=...)`, deletes the temp
  file, renders the result). No new pipeline logic — the dashboard is a thin view over
  the exact same `run_pipeline()` the CLI uses, so the two can't drift apart
  - Extended `main.run_pipeline()`'s return dict with a new `timeline` key (per-game
    trend rows as `list[dict]`, via `trend_df.to_dict(orient="records")`) — additive
    only, no existing keys changed, needed for the dashboard's table/chart
  - `_build_trend_chart()` turns the timeline into plain SVG polyline coordinates
    (no JS charting library) — returns `None` if fewer than 2 games, so the page
    correctly shows "not enough games yet" instead of an empty/broken chart
- `src/webapp/templates/{base,index,report}.html`: styled per Design.md — dark hero
  section, saffron/green accents, Playfair Display headings, DM Sans body, DM Mono for
  all numeric/data values, training-plan cards color-coded by whether a weakness is
  "persistent"
- `tests/test_webapp.py`: 5 tests via Flask's test client — index loads, missing-file
  and invalid-PGN error paths both show a clear message (not a stack trace), a real PGN
  upload renders the coaching report + training plan, a multi-game PGN renders an actual
  trend-line chart. Also manually verified by running the real dev server
  (`python -m src.webapp.app`) and hitting it with `curl`, including a real file upload
  producing a full styled HTML report (confirmed 200 OK, correct content, correct
  fallbacks) — full suite (51 tests total including this file) passes

**In progress / broken:**
- None. Not manually verified in an actual browser (this sandbox has no GUI browser)
  — verified via `curl`/Flask test client instead, which covers the same HTTP
  request/response path a browser would use, but you should still open
  `http://127.0.0.1:5000` yourself locally to eyeball the styling

**Decisions made:**
- **This deviates from Rules.md's "do not add a web framework (Flask/Django/FastAPI)
  unless Phases.md explicitly reaches a 'build the UI' phase."** No such phase was
  reached — Phase 7's web view was explicitly optional/stretch and was not built as
  part of Phases 0-7. The user then explicitly asked for a local-only dashboard with
  file upload, which is a direct instruction overriding that default constraint for
  this one addition. Recording it here per Rules.md §3's own instruction to document
  (not silently make) any decision that deviates from the project docs. Architecture.md
  §3 was updated to list the new `src/webapp/` folder and explain why it's there
- Chose Flask over FastAPI/Django: smallest, most standard choice for a single-purpose
  local dashboard with no auth/API/database — nothing else in the stack needed
- Chart is hand-built inline SVG rather than a JS charting library (matplotlib, Chart.js,
  etc.) — keeps the dashboard dependency-free beyond Flask itself and avoids adding
  another new dependency for one line chart
- Kept it explicitly single-user/local-only: binds to `127.0.0.1` (not `0.0.0.0`), no
  auth, no database, no session/multi-user state — consistent with PRD.md's non-goals
  even though a web framework is now present
- Default analysis depth in the dashboard is 10 (vs. the CLI's 12) and clamped to
  [4, 18] via the form — favors a responsive browser request/response cycle over the
  CLI's slightly higher-accuracy default

**Next step:**
- Have the user run `python -m src.webapp.app` locally and open
  `http://127.0.0.1:5000` in a real browser to confirm the styling reads correctly and
  upload their own real PGN files
- If they want the dashboard to also support pulling by username (not just file
  upload), that's a small addition to `index.html`/`app.py` reusing
  `run_pipeline(username=..., source=...)`, not yet built since the request was
  specifically "upload any game pgn"

---

### 2026-09-18 — Phase 7: Integration & Polish (PROJECT COMPLETE through Phases 0-7)
**Completed:**
- `src/main.py`: `run_pipeline()` orchestrates ingestion -> annotation -> features -> weakness
  -> NLP -> recommendation end to end, returning `{text_report, report_source, training_plan,
  games_analyzed, persistent_weaknesses, ranked_weaknesses}` (matches Architecture.md §4's final
  Recommendation->Output contract, extended with run metadata). `main()` is an `argparse` CLI
  (`--username`/`--pgn-file` mutually exclusive, `--source`, `--max-games`, `--depth`) — no web
  framework used, per Rules.md
- Added a full pytest suite under `tests/` with one file per module (`test_ingestion.py`,
  `test_annotation.py`, `test_features.py`, `test_weakness.py`, `test_nlp.py`,
  `test_recommend.py`, `test_main.py`, plus `conftest.py`) — 41 tests, all passing. Kept the six
  `test_phaseN_smoke.py` narrative scripts from Phases 0-6 as executable walkthroughs (still all
  passing); the pytest suite is the more granular per-module coverage Phase 7 asks for
  specifically
- `test_main.py::test_cli_runs_as_a_single_command` runs `python -m src.main --pgn-file ...` as
  an actual subprocess — the literal "one command in, full report + training plan out, no manual
  steps" done-when criterion — confirmed passing, output contains both the coaching report and
  the training plan
- Added `pytest>=7.0.0` to `requirements.txt` (dev/test dependency)

**In progress / broken:**
- Two things remain unverified against live external services in this sandboxed session,
  both already flagged in their originating phase's entry above and both fully implemented
  against the real, documented API shape: (1) live Chess.com/Lichess API pulls (Phase 1;
  network blocked here, verified via mocks) and (2) the live Anthropic LLM report path (Phase 5;
  no `ANTHROPIC_API_KEY` in this environment, verified via its documented template fallback).
  Recommend both be exercised locally before treating the project as fully proven end-to-end
  with live services
- `src/weakness/lstm_model.py` (Phase 4's stretch goal) was not built — Phases.md marks it
  optional and it was correctly not required for any phase's done-when criterion
- Optional/stretch Phase 7 web view was not built — Design.md's visual system was applied
  instead to this text-based CLI report's structure (hero-style title, summary stats, narrative,
  training-plan cards map onto Design.md §4's sections); a styled HTML/web report is a natural
  follow-up if desired, but Rules.md keeps this CLI/notebook-first unless explicitly asked

**Decisions made:**
- Used `pytest` (a standard, non-web, non-DB testing tool) for the per-module suite required by
  Phase 7 — does not conflict with any Rules.md "avoid" item
- Kept both test styles: the pytest suite (fast, granular, CI-friendly) and the original
  `test_phaseN_smoke.py` scripts (narrative, print real output for human inspection) — the
  latter were valuable during development for literally seeing the pipeline's output at each
  stage and are cheap to keep

**Next step:**
- Project is functionally complete through all required (non-stretch) phases. If continuing:
  (1) verify live Chess.com/Lichess pulls and the live LLM report path locally with real
  credentials/network, (2) consider the Phase 4 LSTM stretch goal or a Design.md-styled HTML
  report as follow-on polish, (3) run the full pipeline against a real player's multi-month game
  history to validate PRD.md's success criterion of "at least 3 distinct, correctly-identified
  recurring weaknesses" (needs >=3 games of real history — `identify_persistent_weaknesses`
  requires `min_games=3` by design, so a single-game smoke test correctly reports zero
  "persistent" weaknesses even though `ranked_weaknesses` still surfaces relative severity)

---

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
