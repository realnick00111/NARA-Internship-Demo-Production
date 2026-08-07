from flask import Flask, abort, jsonify, redirect, request, url_for

from db import log_storage_event
from rendering import render_page
from repositories.assessments import delete_assessments_by_ids, get_assessment_row_by_id, upsert_assessment_fields
from services.assessment_workflows import build_assessment_fields, create_assessment_entry, save_assignment_draft
from session_state import clear_current_assessment, get_current_assessment, set_current_assessment


def register_routes(app: Flask) -> None:
    @app.route("/")
    def index():
        return redirect(url_for("screen", screen_id="agency-dashboard"))

    @app.route("/screens/<screen_id>")
    def screen(screen_id: str):
        return render_page(screen_id)

    @app.route("/assessments/new")
    def start_new_assessment():
        clear_current_assessment()
        return redirect(url_for("screen", screen_id="new-assessment"))

    @app.route("/assessments/<int:assessment_id>/create-assessment")
    def open_assessment_create_assessment(assessment_id: int):
        assessment_row = get_assessment_row_by_id(assessment_id)
        if assessment_row is None:
            abort(404)

        set_current_assessment(assessment_id)
        return redirect(url_for("screen", screen_id="assessment-progress"))

    @app.route("/api/save-log", methods=["POST"])
    def save_log():
        data = request.get_json(silent=True) or {}
        user_input = data.get("log_data")

        if user_input:
            log_storage_event(f"save-log payload: {user_input}")
            return jsonify({"status": "success", "message": "Log saved successfully!"})

        return jsonify({"status": "error", "message": "No data provided"}), 400

    @app.route("/api/save-assignment-draft", methods=["POST"])
    def save_assignment_draft_api():
        draft_data = request.get_json(silent=True) or {}

        if draft_data:
            try:
                save_assignment_draft(draft_data)
            except ValueError as error:
                return jsonify({"status": "error", "message": str(error)}), 400

            return jsonify({"status": "success", "message": "Draft saved successfully!"})

        return jsonify({"status": "error", "message": "No draft data provided"}), 400

    @app.route("/api/assessments/delete", methods=["POST"])
    def delete_assessments():
        payload = request.get_json(silent=True) or {}
        assessment_ids = payload.get("assessment_ids") or []

        if not isinstance(assessment_ids, list):
            return jsonify({"status": "error", "message": "assessment_ids must be a list"}), 400

        try:
            normalized_ids = [int(assessment_id) for assessment_id in assessment_ids]
        except (TypeError, ValueError):
            return jsonify({"status": "error", "message": "assessment_ids must contain valid integers"}), 400

        if not normalized_ids:
            return jsonify({"status": "error", "message": "No assessments selected"}), 400

        deleted_count = delete_assessments_by_ids(normalized_ids)

        if get_current_assessment() in normalized_ids:
            clear_current_assessment()

        return jsonify({"status": "success", "deleted_count": deleted_count})

    @app.route("/api/assessments/start", methods=["POST"])
    def start_assessment():
        assessment_data = request.get_json(silent=True) or {}

        if not assessment_data:
            return jsonify({"status": "error", "message": "No assessment data provided"}), 400

        current_assessment_id = get_current_assessment()
        current_assessment_row = (
            get_assessment_row_by_id(int(current_assessment_id)) if current_assessment_id is not None else None
        )

        try:
            if current_assessment_row is not None:
                existing_status = str(current_assessment_row["status"] or "not implemented").strip() or "not implemented"
                fields = build_assessment_fields(
                    assessment_data,
                    status=existing_status,
                    existing_assessment=current_assessment_row,
                )
                assessment_id = upsert_assessment_fields(fields, assessment_id=int(current_assessment_row["id"]))
            else:
                assessment_id = create_assessment_entry(assessment_data)
        except ValueError as error:
            return jsonify({"status": "error", "message": str(error)}), 400

        set_current_assessment(assessment_id)
        return jsonify(
            {
                "status": "success",
                "assessment_id": assessment_id,
                "current_assessment_id": get_current_assessment(),
                "next_screen": url_for("screen", screen_id="facility-identification"),
            }
        )
