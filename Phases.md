# ChessMentorNLP — Phases.md

Build order. Each phase should be functionally complete and testable before moving to the
next. Do not start a phase until the previous one's "Done when" criteria are met.

## Phase 0 — Environment Setup
- Install Python 3.10+, `python-chess`, `stockfish` binary + wrapper, `pandas`, `numpy`,
  `requests`
- Verify Stockfish runs and returns an evaluation for a test FEN
- Set up folder structure per Architecture.md
- **Done when:** a sample PGN can be loaded and one position can be evaluated by Stockfish

## Phase 1 — Data Ingestion
- Implement `fetch_games.py` (Chess.com and/or Lichess API pull) and `parse_pgn.py`
- Support both API pull (by username) and manual PGN file upload
- **Done when:** you can pull your own last N games and get a list of parsed game objects

## Phase 2 — Engine Annotation
- Implement `engine.py`: per-move Stockfish evaluation before/after each move
- Implement `classify_moves.py`: convert eval swing → quality label (blunder/mistake/
  inaccuracy/good)
- Save output as a per-move DataFrame (per the data contract in Architecture.md)
- **Done when:** a full game produces a labeled move-by-move table with no crashes

## Phase 3 — Feature Extraction
- Implement `positional.py`: material balance, king safety, pawn structure, game phase
- Implement `motifs.py`: fork/pin/skewer detection (scope to these 3 only)
- Implement `openings.py`: ECO code lookup for first 8–10 moves
- **Done when:** every move row has full positional features + motif tags where applicable

## Phase 4 — Weakness Modeling
- Implement `vectorize.py`: per-game weakness vector from the annotated+featured data
- Implement `aggregate.py`: rolling/EWM trend tracking across games, chronologically
- **Stretch:** implement `lstm_model.py` for sequence-based trend prediction
- **Done when:** given a chronological batch of games, you get a timeline showing at least
  one clearly identifiable persistent weakness pattern

## Phase 5 — NLP Report Generation
- Implement `templates.py`: move-to-text templating (baseline, deterministic)
- Implement `report_generator.py`: LLM-based natural-language coaching report from the
  weakness vector + trend data
- **Done when:** running the pipeline on a real player produces a coherent multi-paragraph
  coaching report, not just printed stats

## Phase 6 — Recommendation Engine
- Implement `recommender.py`: map weakness tags → Lichess puzzle themes / opening study /
  endgame drills
- **Done when:** each identified weakness in the report links to at least one concrete
  training suggestion

## Phase 7 — Integration & Polish
- Wire everything through `main.py` as a single end-to-end pipeline
- Add basic tests per module (tests/)
- (Optional/stretch) simple CLI or minimal web view per Design.md
- **Done when:** one command takes a username in and produces a full report + training plan
  out, with no manual steps in between

## Notes on sequencing
- Do not attempt Phase 4's LSTM or Phase 5's LLM integration before Phases 1–3 are solid —
  garbage annotation/features data makes both of those a waste of time
- If short on time before a deadline, the safe cut order is: LSTM (Phase 4 stretch) first,
  then LLM-based generation falls back to templates (Phase 5A only), then motif detection
  can shrink to fork-only if needed
