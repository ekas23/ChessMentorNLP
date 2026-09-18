# ChessMentorNLP — Design.md

Applies to any visual output: the optional web view (Phase 7 stretch), generated report
pages/PDFs, or presentation slides. If the deliverable stays CLI/notebook-only, this file
mainly governs report formatting and any slides for Review presentations.

## 1. Visual Direction
Polished, editorial feel rather than a generic dashboard — this is a coaching report, so it
should read like a well-designed document/publication, not a raw stats page.

- Dark hero/header sections for report title pages and section dividers
- Saffron and green as accent colors (used sparingly — for highlights, key stats, section
  markers — not as full backgrounds)
- Clean, generous whitespace; data-heavy sections (weakness tables, trend charts) get a
  lighter background for readability

## 2. Color Palette

| Role | Color |
|---|---|
| Hero/dark background | `#141414` – `#1C1C1C` (near-black) |
| Primary accent (saffron) | `#FF9933` |
| Secondary accent (green) | `#138808` |
| Body background | `#FAFAF8` (off-white) |
| Body text | `#1C1C1C` |
| Muted/secondary text | `#6B6B6B` |
| Success/good move indicator | Secondary accent green |
| Warning/blunder indicator | A muted red, e.g. `#C0392B` (kept separate from the saffron/green identity colors so it reads as a genuine alert) |

## 3. Typography

| Use | Font |
|---|---|
| Headings / hero titles | Playfair Display |
| Body text / UI | DM Sans |
| Code, FEN strings, engine output, move notation | DM Mono |

- Headings: Playfair Display, bold, larger scale for hero sections (e.g., report title, player name)
- Body copy: DM Sans, regular weight, comfortable line-height (1.5–1.6) for report paragraphs
- Any raw data — move lists, PGN snippets, evaluation numbers — always in DM Mono to visually
  distinguish "data" from "narrative" in the report

## 4. Layout Notes for the Coaching Report
- **Hero section**: dark background, player name/handle, date range analyzed, Playfair
  Display title (e.g., "Your Longitudinal Weakness Report")
- **Summary strip**: 2–4 key stats (games analyzed, top weakness, trend direction) in
  saffron/green accent callouts
- **Narrative section**: the LLM-generated coaching report, body copy on light background
- **Data section**: weakness vector table / trend chart, DM Mono for any numeric or notation
  content
- **Recommendations section**: puzzle/training links as distinct cards, using the accent
  colors to differentiate by weakness category

## 5. Charts
- Trend lines (weakness over time): use the saffron/green pair for at most 2 series;
  additional series should use muted neutral tones rather than introducing new hues
- Keep chart backgrounds light even when embedded in a dark-themed page, for readability
