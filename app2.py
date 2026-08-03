import sqlite3
from pathlib import Path

from flask import Flask, abort, jsonify, redirect, render_template, request, url_for
from markupsafe import Markup

app = Flask(__name__)

ROOT = Path(__file__).resolve().parent
TEMPLATES_DIR = ROOT / "templates"
DATA_STORAGE_DIR = ROOT / "Data"
NEW_WEBSITE_DIR = TEMPLATES_DIR / "New Website"
PARTIALS_DIR = NEW_WEBSITE_DIR / "partials"
SCREENS_DIR = NEW_WEBSITE_DIR / "screens"

SCREEN_ORDER = [
    "login-tenant",
    "agency-dashboard",
    "assessment-list",
    "new-assessment",
    "facility-identification",
    "assessment-progress",
    "ch-structural-entry",
    "pqi-findings-entry",
    "pqi3-sample",
    "pqi6-8-hierarchy",
    "pqi9-10-timed",
    "validation-summary",
    "calculation-review",
    "result-summary",
    "detailed-explanation",
    "draft-management",
    "regulation-library",
    "model-administration",
    "import-review",
    "audit-history",
    "export-preview",
]

NAV_BY_SCREEN = {
    "agency-dashboard": "dashboard",
    "assessment-list": "assessments",
    "new-assessment": "assessments",
    "facility-identification": "assessments",
    "assessment-progress": "assessments",
    "ch-structural-entry": "assessments",
    "pqi-findings-entry": "assessments",
    "pqi3-sample": "assessments",
    "pqi6-8-hierarchy": "assessments",
    "pqi9-10-timed": "assessments",
    "validation-summary": "assessments",
    "calculation-review": "assessments",
    "result-summary": "assessments",
    "detailed-explanation": "assessments",
    "draft-management": "drafts",
    "regulation-library": "regulation-library",
    "model-administration": "scoring-models",
    "import-review": "regulation-library",
    "audit-history": "assessments",
}

STANDALONE_SCREENS = {"login-tenant", "export-preview"}

def read_fragment(fragment_path: Path) -> str:
    return fragment_path.read_text(encoding="utf-8")


def render_screen_section(screen_id: str) -> str:
    screen_path = SCREENS_DIR / f"{screen_id}.html"
    content = read_fragment(screen_path)

    if screen_id in STANDALONE_SCREENS:
        inner_html = content
    else:
        inner_html = render_template(
            "New Website/partials/_shell_routes.html",
            active_nav=NAV_BY_SCREEN.get(screen_id, "assessments"),
            page_head=Markup(""),
            page_content=Markup(content),
        )

    return f'<section class="screen" id="{screen_id}">{inner_html}</section>'


def get_db_connection():
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    return conn


def render_page(screen_id: str) -> str:
    if screen_id not in SCREEN_ORDER:
        abort(404)

    head = read_fragment(PARTIALS_DIR / "_head.html")
    viewer = read_fragment(PARTIALS_DIR / "_viewer.html")
    tail = read_fragment(PARTIALS_DIR / "_tail.html")
    screen_section = render_screen_section(screen_id)
    return head + viewer + screen_section + tail


@app.route("/")
def index():
    return redirect(url_for("screen", screen_id="assessment-list"))


@app.route("/screens/<screen_id>")
def screen(screen_id: str):
    return render_page(screen_id)


@app.route("/api/save-log", methods=["POST"])
def save_log():
    data = request.json
    user_input = data.get("log_data")

    if user_input:
        conn = get_db_connection()
        conn.execute("INSERT INTO logs (user_data) VALUES (?)", (user_input,))
        conn.commit()
        conn.close()
        return jsonify({"status": "success", "message": "Log saved successfully!"})

    return jsonify({"status": "error", "message": "No data provided"}), 400


if __name__ == "__main__":
    app.run(debug=True)