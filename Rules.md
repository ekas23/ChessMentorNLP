# ChessMentorNLP — Rules.md

Boundaries for any AI assistant (Claude, Copilot, etc.) working on this codebase.

## 1. Libraries — Use / Avoid

**Use:**
- `python-chess` for all board/move/PGN handling — never hand-roll chess move legality or
  FEN parsing
- `stockfish` (pip wrapper) or direct UCI subprocess for engine calls — don't implement a
  custom evaluation function
- `pandas`/`numpy` for all tabular data — don't use raw Python lists/dicts for anything that
  will grow beyond a few hundred rows
- `torch` only for the Phase-4 LSTM stretch goal — don't introduce it earlier "just in case"

**Avoid:**
- Do not add a database (Postgres/MongoDB/etc.) — local CSV/Parquet/SQLite is sufficient for
  this project's scale. Adding a DB is scope creep.
- Do not add a web framework (Flask/Django/FastAPI) unless Phases.md explicitly reaches a
  "build the UI" phase — keep the pipeline CLI/notebook-first
- Do not swap Stockfish for a different engine without discussing — evaluation consistency
  matters for the weakness vectors to be comparable over time
- Do not introduce a new NLP/LLM dependency without checking it against Design.md and API
  cost/availability constraints

## 2. Error Handling
- Every external call (Chess.com/Lichess API, Stockfish subprocess) must be wrapped in
  try/except with a clear log message — never let the pipeline crash silently on one bad game
- If a single game fails to parse or annotate, skip it and log it — don't halt the whole batch
- Validate that a FEN/PGN is well-formed before passing it downstream; fail fast with a clear
  error rather than propagating `None` silently through the pipeline

## 3. What the AI Should Do
- Follow the folder structure in Architecture.md exactly — new files go in the layer they
  belong to, not dumped in `src/` root
- Write functions that match the data contracts in Architecture.md section 4 — input/output
  shapes should stay consistent across layers
- Add a docstring to every function stating input shape, output shape, and purpose
- Update Memory.md after completing any phase or meaningful chunk of work (see Memory.md)
- Ask before making an architectural decision not already covered in these docs (e.g.,
  choosing a specific motif-detection algorithm)

## 4. What the AI Should NOT Do
- Do not rewrite or restructure existing working modules "for style" without being asked
- Do not silently change the weakness vector schema once Phase 4 data exists — this breaks
  longitudinal comparability; propose changes explicitly first
- Do not fabricate chess domain facts (opening names, motif definitions) — verify against
  `python-chess` behavior or a real ECO table
- Do not skip ahead to later phases (see Phases.md) before earlier ones are functionally done
- Do not add authentication, multi-user support, or cloud deployment — out of scope per PRD.md

## 5. Code Style
- Type hints on all function signatures
- One module = one responsibility (matches the folder structure)
- No global mutable state — pass data explicitly between pipeline stages
- Prefer explicit over clever — this is a course/research project that needs to be explainable
  in a report, not a production system optimized for brevity
