import json
import sqlite3
from datetime import datetime
from pathlib import Path

from flask import Flask, abort, jsonify, redirect, render_template, request, url_for
from markupsafe import Markup

app = Flask(__name__)

ROOT = Path(__file__).resolve().parent
TEMPLATES_DIR = ROOT / "templates"
DATA_STORAGE_DIR = ROOT / "data"
PARTIALS_DIR = TEMPLATES_DIR / "partials"
SCREENS_DIR = TEMPLATES_DIR / "screens"
DB_PATH = DATA_STORAGE_DIR / "database.db"
LOGS_PATH = DATA_STORAGE_DIR / "logs.txt"

DATABASE_TABLES = {
    "facilities": "facilities",
    "assessments": "assessments",
}

SCREEN_ORDER = [
    "login-tenant",
    "agency-dashboard",
    "assessment-list",
    "new-assessment",
    "new-assignment",
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
    "new-assignment": "assessments",
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

NEW_ASSIGNMENT_FIELDS_PATH = DATA_STORAGE_DIR / "new-assessment-fields.json"

# region rendering

def read_fragment(fragment_path: Path) -> str:
    return fragment_path.read_text(encoding="utf-8")

def render_screen_section(screen_id: str) -> str:
    screen_path = SCREENS_DIR / f"{screen_id}.html"
    content = read_fragment(screen_path)

    if screen_id in STANDALONE_SCREENS:
        inner_html = content
    else:
        inner_html = render_template(
            "partials/_shell_routes.html",
            active_nav=NAV_BY_SCREEN.get(screen_id, "assessments"),
            page_head=Markup(""),
            page_content=Markup(content),
        )

    return f'<section class="screen" id="{screen_id}">{inner_html}</section>'

def render_page(screen_id: str) -> str:
    if screen_id not in SCREEN_ORDER:
        abort(404)        
    head = read_fragment(PARTIALS_DIR / "_head.html")
    viewer = read_fragment(PARTIALS_DIR / "_viewer.html")
    tail = read_fragment(PARTIALS_DIR / "_tail.html")
    screen_section = render_screen_section(screen_id)
    return head + viewer + screen_section + tail

# endregion rendering

# region storage and logging

def log_storage_event(message: str) -> None:
    DATA_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().isoformat(timespec="seconds")
    with LOGS_PATH.open("a", encoding="utf-8") as log_file:
        log_file.write(f"[{timestamp}] {message}\n")

def clear_logs() -> None:
    if LOGS_PATH.exists():
        LOGS_PATH.unlink()
        log_storage_event("Cleared all logs.")

def ensure_storage_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS facilities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS assessments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()

def get_db_connection():
    DATA_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    if not DB_PATH.exists():
        log_storage_event(f"Created missing database at {DB_PATH.name}")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    ensure_storage_schema(conn)
    return conn

def add_database_entry(table_name: str, payload: str) -> None:
    if table_name not in DATABASE_TABLES:
        raise ValueError(f"Unknown table '{table_name}'. Expected one of: {', '.join(DATABASE_TABLES)}")

    conn = get_db_connection()
    try:
        conn.execute(f"INSERT INTO {table_name} (data) VALUES (?)", (payload,))
        conn.commit()
        log_storage_event(f"Added entry to {table_name} table: {payload}")
    finally:
        conn.close()


def save_assignment_draft(draft_data: dict) -> None:
    log_storage_event(f"Received assignment draft payload: {json.dumps(draft_data, sort_keys=True)}")

# endregion storage and logging

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
        add_database_entry("assessments", str(user_input))
        return jsonify({"status": "success", "message": "Log saved successfully!"})

    return jsonify({"status": "error", "message": "No data provided"}), 400


@app.route("/api/save-assignment-draft", methods=["POST"])
def save_assignment_draft_api():
    draft_data = request.get_json(silent=True) or {}

    if draft_data:
        save_assignment_draft(draft_data)
        return jsonify({"status": "success", "message": "Draft received successfully!"})

    return jsonify({"status": "error", "message": "No draft data provided"}), 400

if __name__ == "__main__":
    app.run(debug=True)