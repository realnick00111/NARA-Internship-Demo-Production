import os
from pathlib import Path

from flask import Flask

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

from db import get_db_connection
from routes import register_routes
from services.assessment_workflows import save_assignment_draft
from session_state import set_current_assessment

BASE_DIR = Path(__file__).resolve().parent
if load_dotenv is not None:
    load_dotenv(BASE_DIR / ".env")
    load_dotenv(BASE_DIR / ".flaskenv")

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY", "dev-only-secret-change-me")
app.config["ENV"] = os.environ.get("FLASK_ENV", "development")

register_routes(app)

if __name__ == "__main__":
    app.run(debug=True)
