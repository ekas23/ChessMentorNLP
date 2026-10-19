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
import math

from flask import Flask, render_template, request

from src.ingestion.fetch_games import (
    DEFAULT_N_GAMES,
    ChessComAPIError,
    ChessComNoPublicGamesError,
    ChessComUsernameNotFoundError,
)
from src.ingestion.game_meta import TIME_CLASSES
from src.main import run_pipeline
from src.nlp.templates import metric_label

logger = logging.getLogger(__name__)

app = Flask(__name__)

DASHBOARD_DEPTH = 14  # fixed, not user-configurable
CHART_WIDTH = 760
CHART_HEIGHT = 220
CHART_PAD_LEFT = 48
CHART_PAD_RIGHT = 16
CHART_PAD_TOP = 16
CHART_PAD_BOTTOM = 32
SERIES_COLOURS = ["#FF9933", "#138808", "#6B6B6B"]  # Design.md: saffron/green, then neutral


def _build_trend_chart(timeline: list[dict], metrics: list[str]) -> dict | None:
    """Input: timeline rows (one per game, with '{metric}_ewm' columns), up to 3 metrics.
    Output: {series: [{label, colour, points}], y_ticks: [{y, label}], x_ticks: [{x, label}],
    width, height} for an SVG line chart, or None with fewer than 2 games.

    Purpose: dependency-free SVG trend chart with labelled axes. The x axis is the game
    number (matching the per-game table), the y axis is % of the player's moves."""
    if len(timeline) < 2 or not metrics:
        return None
    metrics = metrics[:3]
    plot_w = CHART_WIDTH - CHART_PAD_LEFT - CHART_PAD_RIGHT
    plot_h = CHART_HEIGHT - CHART_PAD_TOP - CHART_PAD_BOTTOM
    all_values = [row.get(f"{m}_ewm") or 0.0 for m in metrics for row in timeline]
    top = max(all_values) or 0.01
    top = math.ceil(top * 100 / 2) * 2 / 100 or 0.02  # round up to a whole even percent
    n = len(timeline)

    def x(i: int) -> float:
        return CHART_PAD_LEFT + plot_w * i / (n - 1)

    def y(v: float) -> float:
        return CHART_PAD_TOP + plot_h * (1 - v / top)

    series = []
    for colour, metric in zip(SERIES_COLOURS, metrics):
        pts = " ".join(f"{x(i):.1f},{y(row.get(f'{metric}_ewm') or 0.0):.1f}" for i, row in enumerate(timeline))
        series.append({"label": metric_label(metric), "colour": colour, "points": pts})
    y_ticks = [{"y": round(y(top * k / 4), 1), "label": f"{top * k / 4 * 100:.1f}%"} for k in range(5)]
    step = max(1, round(n / 8))
    x_ticks = [{"x": round(x(i), 1), "label": str(i + 1)} for i in range(0, n, step)]
    if x_ticks[-1]["label"] != str(n):
        x_ticks.append({"x": round(x(n - 1), 1), "label": str(n)})
    return {"series": series, "y_ticks": y_ticks, "x_ticks": x_ticks, "width": CHART_WIDTH,
            "height": CHART_HEIGHT, "left": CHART_PAD_LEFT, "right": CHART_WIDTH - CHART_PAD_RIGHT,
            "bottom": CHART_HEIGHT - CHART_PAD_BOTTOM}


@app.route("/", methods=["GET"])
def index():
    """Input shape: none (GET request). Output shape: rendered HTML (the input form).
    Purpose: landing page where the user enters a Chess.com username and a game count.
    """
    return render_template("index.html", default_n_games=DEFAULT_N_GAMES, time_classes=TIME_CLASSES)


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
        return render_template("index.html", default_n_games=DEFAULT_N_GAMES, time_classes=TIME_CLASSES, error="Please enter a Chess.com username.")

    try:
        max_games = int(request.form.get("max_games", DEFAULT_N_GAMES))
    except ValueError:
        max_games = DEFAULT_N_GAMES
    max_games = max(1, min(max_games, 500))  # keep runtime sane in a browser request/response cycle

    time_class = request.form.get("time_class") or "all"
    if time_class not in TIME_CLASSES:
        time_class = "all"

    try:
        result = run_pipeline(username=username, max_games=max_games, depth=DASHBOARD_DEPTH,
                              time_class=None if time_class == "all" else time_class)
    except ChessComUsernameNotFoundError:
        error = f"Chess.com username '{username}' was not found. Check the spelling and try again."
        logger.warning(error)
        return render_template("index.html", default_n_games=DEFAULT_N_GAMES, time_classes=TIME_CLASSES, error=error)
    except ChessComNoPublicGamesError:
        error = f"'{username}' has no public games available (private or empty profile)."
        logger.warning(error)
        return render_template("index.html", default_n_games=DEFAULT_N_GAMES, time_classes=TIME_CLASSES, error=error)
    except ChessComAPIError as exc:
        error = f"Chess.com API request failed: {exc}"
        logger.warning(error)
        return render_template("index.html", default_n_games=DEFAULT_N_GAMES, time_classes=TIME_CLASSES, error=error)
    except Exception as exc:
        logger.warning("Dashboard analysis failed for username '%s': %s", username, exc)
        return render_template(
            "index.html",
            default_n_games=DEFAULT_N_GAMES,
            time_classes=TIME_CLASSES,
            error=f"Could not analyze '{username}': {exc}",
        )

    return render_template(
        "report.html",
        player_name=username,
        result=result,
        chart=_build_trend_chart(result["timeline"], result["persistent_weaknesses"] or ["blunder_rate"]),
        metric_label=metric_label,
    )


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
