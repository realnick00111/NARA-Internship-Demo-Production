import os

from flask import Flask

from db import get_db_connection
from routes import register_routes
from services.assessment_workflows import save_assignment_draft
from session_state import set_current_assessment

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY", "dev-only-secret-change-me")

register_routes(app)

if __name__ == "__main__":
    app.run(debug=True)
