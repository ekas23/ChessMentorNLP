"""Local-only web dashboard for ChessMentorNLP: enter a Chess.com username and
a number of games, get the same coaching report + training plan the CLI
(src/main.py) produces, rendered as a styled page per Design.md.

This module is an explicit, user-requested addition on top of the phased
build in Phases.md/Rules.md -- Rules.md normally restricts adding a web
framework unless a phase calls for building a UI, which none of the required
phases did. This deviation is documented in Memory.md per Rules.md §3's
instruction to record (not silently make) any such decision. It reuses
src.main.run_pipeline() rather than reimplementing any pipeline logic, so the
dashboard and the CLI can never drift out of sync on how a report is built.

Single-input model (2026-09-21 scope change, see Memory.md): the form below
takes exactly a Chess.com username and a game count -- no PGN file upload,
no source selection. The earlier PGN-upload version of this dashboard has
been removed entirely, not just hidden.

Run locally with:
    python -m src.webapp.app
then open http://127.0.0.1:5000 in a browser. Never exposed beyond localhost
by default (Rules.md: no auth/multi-user/cloud deployment -- this is a
single-player, local-first tool).
"""

import logging

from flask import Flask, render_template, request

from src.ingestion.fetch_games import (
    DEFAULT_N_GAMES,
    ChessComAPIError,
    ChessComNoPublicGamesError,
    ChessComUsernameNotFoundError,
)
from src.main import run_pipeline

logger = logging.getLogger(__name__)

app = Flask(__name__)

DASHBOARD_DEPTH = 10  # fixed, not user-configurable -- see Memory.md ("no other fields")
CHART_METRIC = "blunder_rate_ewm"
CHART_WIDTH = 760
CHART_HEIGHT = 140
CHART_PAD = 24


def _build_trend_chart(timeline: list[dict], metric: str = CHART_METRIC) -> dict | None:
    """Input shape: timeline (list[dict], the 'timeline' entry from run_pipeline()'s
    result -- one dict per game with trend columns like 'blunder_rate_ewm'), metric str
    (the column to chart).
    Output shape: dict {points: str (an SVG <polyline> points attribute), labels:
    list[str] (one short label per game, evenly sampled), max_value: float} or None if
    there are fewer than 2 games (a single point can't show a trend).

    Purpose: turn the pipeline's per-game trend data into plain SVG coordinates so the
    report page can render a dependency-free trend line (no JS charting library needed
    for a local dashboard), per Design.md's chart guidance (saffron/green, light background).
    """
    values = [row.get(metric) for row in timeline if row.get(metric) is not None]
    if len(values) < 2:
        return None

    max_value = max(values) or 1.0
    usable_width = CHART_WIDTH - 2 * CHART_PAD
    usable_height = CHART_HEIGHT - 2 * CHART_PAD
    step = usable_width / (len(values) - 1)

    points = []
    for i, value in enumerate(values):
        x = CHART_PAD + i * step
        y = CHART_PAD + usable_height * (1 - value / max_value)
        points.append(f"{x:.1f},{y:.1f}")

    label_count = min(6, len(timeline))
    label_indices = sorted(set(round(i * (len(timeline) - 1) / max(label_count - 1, 1)) for i in range(label_count)))
    labels = [timeline[i].get("date") or f"game {i + 1}" for i in label_indices]

    return {"points": " ".join(points), "labels": labels, "max_value": max_value}


@app.route("/", methods=["GET"])
def index():
    """Input shape: none (GET request). Output shape: rendered HTML (the input form).
    Purpose: landing page where the user enters a Chess.com username and a game count.
    """
    return render_template("index.html", default_n_games=DEFAULT_N_GAMES)


@app.route("/analyze", methods=["POST"])
def analyze():
    """Input shape: form POST with 'username' (str, required) and 'max_games' (int,
    optional, defaults to DEFAULT_N_GAMES) fields. No file field -- PGN upload was
    removed entirely per the 2026-09-21 scope change (see Memory.md).
    Output shape: rendered HTML (the coaching report page) or the input form
    re-rendered with a clear error message.

    Purpose: run the full pipeline via src.main.run_pipeline() for the given
    username/game-count and render the result. Every failure mode (missing
    username, username not found, private/empty profile, a Chess.com API
    failure, or any other pipeline error) is caught and shown to the user as a
    clear message rather than a stack trace or a silent crash, per Rules.md
    §2's error-handling requirement.
    """
    username = (request.form.get("username") or "").strip()
    if not username:
        return render_template("index.html", default_n_games=DEFAULT_N_GAMES, error="Please enter a Chess.com username.")

    try:
        max_games = int(request.form.get("max_games", DEFAULT_N_GAMES))
    except ValueError:
        max_games = DEFAULT_N_GAMES
    max_games = max(1, min(max_games, 500))  # keep runtime sane in a browser request/response cycle

    try:
        result = run_pipeline(username=username, max_games=max_games, depth=DASHBOARD_DEPTH)
    except ChessComUsernameNotFoundError:
        error = f"Chess.com username '{username}' was not found. Check the spelling and try again."
        logger.warning(error)
        return render_template("index.html", default_n_games=DEFAULT_N_GAMES, error=error)
    except ChessComNoPublicGamesError:
        error = f"'{username}' has no public games available (private or empty profile)."
        logger.warning(error)
        return render_template("index.html", default_n_games=DEFAULT_N_GAMES, error=error)
    except ChessComAPIError as exc:
        error = f"Chess.com API request failed: {exc}"
        logger.warning(error)
        return render_template("index.html", default_n_games=DEFAULT_N_GAMES, error=error)
    except Exception as exc:
        logger.warning("Dashboard analysis failed for username '%s': %s", username, exc)
        return render_template(
            "index.html",
            default_n_games=DEFAULT_N_GAMES,
            error=f"Could not analyze '{username}': {exc}",
        )

    return render_template(
        "report.html",
        player_name=username,
        result=result,
        chart=_build_trend_chart(result["timeline"]),
        chart_width=CHART_WIDTH,
        chart_height=CHART_HEIGHT,
    )


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
