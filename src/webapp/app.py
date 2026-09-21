"""Local-only web dashboard for ChessMentorNLP: upload a PGN, get the same
coaching report + training plan the CLI (src/main.py) produces, rendered as a
styled page per Design.md.

This module is an explicit, user-requested addition on top of the phased
build in Phases.md/Rules.md -- Rules.md normally restricts adding a web
framework unless a phase calls for building a UI, which none of the required
phases did. This deviation is documented in Memory.md per Rules.md §3's
instruction to record (not silently make) any such decision. It reuses
src.main.run_pipeline() rather than reimplementing any pipeline logic, so the
dashboard and the CLI can never drift out of sync on how a report is built.

Run locally with:
    python -m src.webapp.app
then open http://127.0.0.1:5000 in a browser. Never exposed beyond localhost
by default (Rules.md: no auth/multi-user/cloud deployment -- this is a
single-player, local-first tool).
"""

import logging
import os
import tempfile

from flask import Flask, render_template, request

from src.main import run_pipeline

logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024  # 5 MB is generously more than any real PGN

DEFAULT_DEPTH = 10  # lower than main.py's CLI default (12) -- favors a responsive browser wait
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
    """Input shape: none (GET request). Output shape: rendered HTML (the upload form).
    Purpose: landing page where the user uploads a PGN file and picks an analysis depth.
    """
    return render_template("index.html", default_depth=DEFAULT_DEPTH)


@app.route("/analyze", methods=["POST"])
def analyze():
    """Input shape: multipart form POST with a 'pgn_file' file field, optional 'player_name'
    and 'depth' fields.
    Output shape: rendered HTML (the coaching report page) or the upload form re-rendered
    with an error message.

    Purpose: save the uploaded PGN to a temp file, run the full pipeline on it via
    src.main.run_pipeline(), and render the result. Every failure mode (no file, empty
    file, a PGN with no valid games, an engine/pipeline error) is caught and shown to
    the user as a clear message rather than a stack trace or a silent crash, per
    Rules.md §2's error-handling requirement.
    """
    uploaded = request.files.get("pgn_file")
    if uploaded is None or uploaded.filename == "":
        return render_template("index.html", default_depth=DEFAULT_DEPTH, error="Please choose a PGN file to upload.")

    player_name = (request.form.get("player_name") or "").strip() or None
    try:
        depth = int(request.form.get("depth", DEFAULT_DEPTH))
    except ValueError:
        depth = DEFAULT_DEPTH
    depth = max(4, min(depth, 18))  # keep runtime sane in a browser request/response cycle

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".pgn", delete=False) as tmp:
            tmp.write(uploaded.read())
            tmp_path = tmp.name

        result = run_pipeline(pgn_file=tmp_path, username=player_name, depth=depth)
    except Exception as exc:
        logger.warning("Dashboard analysis failed for upload '%s': %s", uploaded.filename, exc)
        return render_template(
            "index.html",
            default_depth=DEFAULT_DEPTH,
            error=f"Could not analyze this PGN: {exc}",
        )
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)

    return render_template(
        "report.html",
        player_name=player_name or uploaded.filename,
        result=result,
        chart=_build_trend_chart(result["timeline"]),
        chart_width=CHART_WIDTH,
        chart_height=CHART_HEIGHT,
    )


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
