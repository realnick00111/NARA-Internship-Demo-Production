import json

from flask import Flask, Response, abort, jsonify, redirect, request, url_for

from constants import PQI10_LIKERT_SCORE_RANGE, PQI10_OBSERVATION_COUNT, PQI2_ENVIRONMENT_QUESTIONS, PQI3_RECORD_COUNT, PQI4_STAFF_FAMILY_OPPORTUNITIES_QUESTIONS, PQI5_CHILD_PROGRESS_QUESTIONS, PQI6_HIERARCHY, PQI7_HIERARCHY, PQI8_HIERARCHY
from db import log_storage_event
from rendering import render_page
from repositories.assessments import (
    delete_assessments_by_ids,
    build_assessment_input_snapshot,
    build_assessment_input_snapshots,
    get_assessment_row_by_id,
    import_assessment_input_snapshot,
    update_assessment_json_fields,
    upsert_assessment_fields,
)
from services.assessment_workflows import build_assessment_fields, create_assessment_entry, save_assignment_draft
from services.screen_contexts import build_calculation_result, build_pqi1_context, build_pqi_access_context, build_validation_context
from services.formatters import (
    calculate_pqi1_score,
    calculate_pqi2_score,
    calculate_pqi3_score,
    calculate_pqi4_score,
    calculate_pqi5_points,
    calculate_pqi6_score_modifier,
    calculate_pqi7_score_modifier,
    calculate_pqi8_score_modifier,
    normalize_yes_no,
)
from session_state import clear_current_assessment, get_current_assessment, set_current_assessment


def calculation_requires_review(result: dict) -> bool:
    try:
        return float(result.get("CALCULATED_CH")) > float(result.get("RWCH_REFERENCE"))
    except (TypeError, ValueError):
        return False


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

    @app.route("/assessments/input-snapshot")
    def download_assessment_input_snapshot():
        assessment_id = get_current_assessment()
        if assessment_id is None:
            return jsonify({"status": "error", "message": "No assessment selected, unable to download snapshot"}), 400

        snapshot = build_assessment_input_snapshot(int(assessment_id))
        if snapshot is None:
            abort(404)

        response = Response(
            json.dumps(snapshot, indent=2, ensure_ascii=True) + "\n",
            mimetype="application/json",
        )
        response.headers["Content-Disposition"] = f"attachment; filename=assessment-input-snapshot-{int(assessment_id):05d}.json"
        return response

    @app.route("/assessments/input-snapshots")
    def download_assessment_input_snapshots():
        response = Response(
            json.dumps(build_assessment_input_snapshots(), indent=2, ensure_ascii=True) + "\n",
            mimetype="application/json",
        )
        response.headers["Content-Disposition"] = "attachment; filename=assessment-input-snapshots.json"
        return response

    @app.route("/api/save-log", methods=["POST"])
    def save_log():
        data = request.get_json(silent=True) or {}
        user_input = data.get("log_data")

        if user_input:
            log_storage_event(f"save-log payload: {user_input}")
            return jsonify({"status": "success", "message": "Log saved successfully!"})

        return jsonify({"status": "error", "message": "No data provided"}), 400

    @app.route("/api/validation-summary")
    def validation_summary_api():
        return jsonify(build_validation_context())

    @app.route("/assessments/calculate", methods=["POST"])
    def calculate_assessment_result():
        validation_context = build_validation_context()
        if validation_context["assessment_id"] is None:
            return jsonify({"status": "error", "message": "No assessment selected, unable to calculate"}), 400
        if validation_context["blocking_errors"]:
            return jsonify({"status": "error", "message": "Complete all required assessment data before calculating"}), 400

        result = build_calculation_result()
        status = "needs review" if calculation_requires_review(result) else "provisional"
        update_assessment_json_fields(validation_context["assessment_id"], calculated_result=result, status=status)
        return redirect(url_for("screen", screen_id="result-summary"))

    @app.route("/assessments/finalize", methods=["POST"])
    def finalize_assessment():
        assessment_id = get_current_assessment()
        assessment_row = get_assessment_row_by_id(assessment_id) if assessment_id is not None else None
        result = json.loads(assessment_row["calculated_result"] or "{}") if assessment_row is not None else {}

        if assessment_row is None:
            return jsonify({"status": "error", "message": "No assessment selected, unable to finalize"}), 400
        if str(assessment_row["status"] or "").strip().lower() != "provisional":
            return jsonify({"status": "error", "message": "Only provisional assessments can be finalized"}), 400
        if not result or calculation_requires_review(result):
            return jsonify({"status": "error", "message": "Assessment requires review before finalization"}), 400

        update_assessment_json_fields(assessment_id, status="final")
        return redirect(url_for("screen", screen_id="result-summary"))

    @app.route("/api/assessments/pqi-progress")
    def pqi_progress_api():
        context = build_pqi1_context()
        nav_items = {
            "pqi-1": {"complete": context["pqi1_complete"], "status": context["pqi1_score_label"]},
            "pqi-2": {"complete": context["pqi2_complete"], "status": context["pqi2_score_label"]},
            "pqi-3": {"complete": context["pqi3_complete"], "status": f"{context['pqi3_completed_count']} of 10 records"},
            "pqi-4": {"complete": context["pqi4_complete"], "status": context["pqi4_score_label"]},
            "pqi-5": {"complete": context["pqi5_complete"], "status": context["pqi5_score_label"]},
            "pqi-6-8": {"complete": context["pqi68_complete"], "status": f"{context['pqi68_complete_count']} of 3 complete"},
            "pqi-9-10": {"complete": context["pqi910_complete"], "status": f"{context['pqi910_complete_count']} of 2 complete"},
        }
        return jsonify(
            {
                "assessment_id": context["editing_assessment_id"],
                "numerator": context["pqi_progress_numerator"],
                "denominator": context["pqi_progress_denominator"],
                "percentage": context["pqi_progress_percentage"],
                "nav_items": nav_items,
            }
        )

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

    @app.route("/api/assessments/contact-hours", methods=["POST"])
    def save_contact_hours_draft_api():
        payload = request.get_json(silent=True) or {}
        contact_hours = payload.get("contact_hours")
        pqi_findings = payload.get("pqi_findings")

        assessment_id = payload.get("assessment_id") or get_current_assessment()
        if assessment_id is None:
            return jsonify({"status": "error", "message": "No assessment selected, unable to save"}), 400

        if not isinstance(contact_hours, dict):
            return jsonify({"status": "error", "message": "contact_hours must be an object"}), 400

        try:
            normalized_assessment_id = int(assessment_id)
            update_assessment_json_fields(
                normalized_assessment_id,
                contact_hours=contact_hours,
                pqi_findings=pqi_findings if isinstance(pqi_findings, dict) else None,
            )
        except (TypeError, ValueError) as error:
            return jsonify({"status": "error", "message": str(error)}), 400

        set_current_assessment(normalized_assessment_id)
        return jsonify({"status": "success", "message": "Contact hours saved successfully!", "assessment_id": normalized_assessment_id})

    @app.route("/api/assessments/pqi1", methods=["POST"])
    def save_pqi1():
        payload = request.get_json(silent=True) or {}
        assessment_id = payload.get("assessment_id") or get_current_assessment()

        if assessment_id is None:
            return jsonify({"status": "error", "message": "No assessment selected, unable to save"}), 400

        certified_teaching_staff = payload.get("certified_teaching_staff")
        total_teaching_staff = payload.get("total_teaching_staff")
        complete_flag = bool(payload.get("complete", False))

        try:
            normalized_certified = int(certified_teaching_staff) if certified_teaching_staff not in (None, "") else None
            normalized_total = int(total_teaching_staff) if total_teaching_staff not in (None, "") else None
        except (TypeError, ValueError):
            return jsonify({"status": "error", "message": "Teaching staff counts must be valid integers"}), 400

        score = calculate_pqi1_score(normalized_certified, normalized_total)
        if complete_flag and score is None:
            return jsonify({"status": "error", "message": "Enter valid teaching staff counts before completing PQI 1"}), 400

        try:
            normalized_assessment_id = int(assessment_id)
            update_assessment_json_fields(
                normalized_assessment_id,
                pqi_findings={
                    "pqi1": {
                        "complete": complete_flag,
                        "score": score,
                        "certified_teaching_staff": normalized_certified,
                        "total_teaching_staff": normalized_total,
                    }
                },
            )
        except (TypeError, ValueError) as error:
            return jsonify({"status": "error", "message": str(error)}), 400

        set_current_assessment(normalized_assessment_id)
        return jsonify(
            {
                "status": "success",
                "message": "PQI 1 saved successfully!",
                "assessment_id": normalized_assessment_id,
                "complete": complete_flag,
                "score": score,
            }
        )

    @app.route("/api/assessments/pqi2", methods=["POST"])
    def save_pqi2():
        payload = request.get_json(silent=True) or {}
        assessment_id = payload.get("assessment_id") or get_current_assessment()

        if assessment_id is None:
            return jsonify({"status": "error", "message": "No assessment selected, unable to save"}), 400

        responses = payload.get("responses")
        if not isinstance(responses, dict):
            return jsonify({"status": "error", "message": "responses must be an object"}), 400

        optional_note = str(payload.get("optional_note", "") or "").strip()
        complete_flag = bool(payload.get("complete", False))
        question_ids = [str(index) for index in range(1, len(PQI2_ENVIRONMENT_QUESTIONS) + 1)]
        normalized_index_responses: dict[str, str | None] = {}

        for raw_key, raw_value in responses.items():
            if not isinstance(raw_key, str):
                continue

            key_text = raw_key.strip()
            normalized_index = None
            if key_text in question_ids:
                normalized_index = key_text
            elif "." in key_text:
                suffix = key_text.rsplit(".", 1)[-1]
                if suffix.isdigit():
                    normalized_index = str(int(suffix))
            if normalized_index in question_ids:
                normalized_index_responses[normalized_index] = normalize_yes_no(raw_value)

        for question_id in question_ids:
            if question_id not in normalized_index_responses:
                normalized_index_responses[question_id] = normalize_yes_no(responses.get(question_id))

        all_answered = all(normalized_index_responses[question_id] in {"yes", "no"} for question_id in question_ids)
        if complete_flag and not all_answered:
            return jsonify({"status": "error", "message": "Answer all PQI 2 questions before completing"}), 400

        ordered_responses = [normalized_index_responses[question_id] for question_id in question_ids]
        score = calculate_pqi2_score(ordered_responses)
        yes_count = sum(1 for value in ordered_responses if value == "yes")
        stored_responses = {f"2.{question_id}": normalized_index_responses[question_id] for question_id in question_ids}

        try:
            normalized_assessment_id = int(assessment_id)
            update_assessment_json_fields(
                normalized_assessment_id,
                pqi_findings={
                    "pqi2": {
                        "complete": complete_flag,
                        "score": score,
                        "question_count": len(question_ids),
                        "yes_count": yes_count,
                        "responses": stored_responses,
                        "optional_note": optional_note,
                    }
                },
            )
        except (TypeError, ValueError) as error:
            return jsonify({"status": "error", "message": str(error)}), 400

        set_current_assessment(normalized_assessment_id)
        return jsonify(
            {
                "status": "success",
                "message": "PQI 2 saved successfully!",
                "assessment_id": normalized_assessment_id,
                "complete": complete_flag,
                "score": score,
                "yes_count": yes_count,
                "question_count": len(question_ids),
            }
        )

    @app.route("/api/assessments/pqi5", methods=["POST"])
    def save_pqi5():
        payload = request.get_json(silent=True) or {}
        assessment_id = payload.get("assessment_id") or get_current_assessment()

        if assessment_id is None:
            return jsonify({"status": "error", "message": "No assessment selected, unable to save"}), 400

        responses = payload.get("responses")
        if not isinstance(responses, dict):
            return jsonify({"status": "error", "message": "responses must be an object"}), 400

        complete_flag = bool(payload.get("complete", False))
        question_ids = [str(index) for index in range(1, len(PQI5_CHILD_PROGRESS_QUESTIONS) + 1)]
        normalized_index_responses: dict[str, str | None] = {}

        for raw_key, raw_value in responses.items():
            if not isinstance(raw_key, str):
                continue

            key_text = raw_key.strip()
            normalized_index = None
            if key_text in question_ids:
                normalized_index = key_text
            elif "." in key_text:
                suffix = key_text.rsplit(".", 1)[-1]
                if suffix.isdigit():
                    normalized_index = str(int(suffix))
            if normalized_index in question_ids:
                normalized_index_responses[normalized_index] = normalize_yes_no(raw_value)

        for question_id in question_ids:
            if question_id not in normalized_index_responses:
                normalized_index_responses[question_id] = normalize_yes_no(responses.get(question_id))

        all_answered = all(normalized_index_responses[question_id] in {"yes", "no"} for question_id in question_ids)
        if complete_flag and not all_answered:
            return jsonify({"status": "error", "message": "Answer all PQI 5 questions before completing"}), 400

        ordered_responses = [normalized_index_responses[question_id] for question_id in question_ids]
        points = calculate_pqi5_points(ordered_responses)
        base_points, bonus_point, total_points = points if points is not None else (None, None, None)
        stored_responses = {f"5.{question_id}": normalized_index_responses[question_id] for question_id in question_ids}

        try:
            normalized_assessment_id = int(assessment_id)
            update_assessment_json_fields(
                normalized_assessment_id,
                pqi_findings={
                    "pqi5": {
                        "complete": complete_flag,
                        "base_points": base_points,
                        "bonus_point": bonus_point,
                        "score": total_points,
                        "responses": stored_responses,
                    }
                },
            )
        except (TypeError, ValueError) as error:
            return jsonify({"status": "error", "message": str(error)}), 400

        set_current_assessment(normalized_assessment_id)
        return jsonify(
            {
                "status": "success",
                "message": "PQI 5 saved successfully!",
                "assessment_id": normalized_assessment_id,
                "complete": complete_flag,
                "base_points": base_points,
                "bonus_point": bonus_point,
                "score": total_points,
            }
        )

    @app.route("/api/assessments/pqi3", methods=["POST"])
    def save_pqi3():
        payload = request.get_json(silent=True) or {}
        assessment_id = payload.get("assessment_id") or get_current_assessment()
        if assessment_id is None:
            return jsonify({"status": "error", "message": "No assessment selected, unable to save"}), 400
        assessment_row = get_assessment_row_by_id(int(assessment_id))
        if assessment_row is None or not build_pqi_access_context(assessment_row)["pqi_allowed"]["3"]:
            return jsonify({"status": "error", "message": "PQI 3 is not available for this facility type"}), 400

        raw_records = payload.get("records")
        if not isinstance(raw_records, dict):
            return jsonify({"status": "error", "message": "records must be an object"}), 400

        normalized_records: dict[str, object] = {}
        for raw_key, raw_record in raw_records.items():
            if not isinstance(raw_key, str):
                continue
            key_text = raw_key.strip()
            if key_text.isdigit():
                normalized_key = f"record {int(key_text)}"
            else:
                normalized_key = key_text
            normalized_records[normalized_key] = raw_record
        raw_records = normalized_records

        records = []
        for index in range(1, PQI3_RECORD_COUNT + 1):
            raw_record = raw_records.get(f"record {index}", {})
            if not isinstance(raw_record, dict):
                raw_record = {}
            record = {
                "emergent_curriculum": normalize_yes_no(raw_record.get("emergent_curriculum")),
                "co_learning": normalize_yes_no(raw_record.get("co_learning")),
                "documented_learning_future_planning": normalize_yes_no(
                    raw_record.get("documented_learning_future_planning", raw_record.get("documentation"))
                ),
                "notes": str(raw_record.get("notes", "") or "").strip(),
            }
            record["complete"] = all(record[field] in {"yes", "no"} for field in (
                "emergent_curriculum", "co_learning", "documented_learning_future_planning"
            ))
            record["positive"] = record["complete"] and all(
                record[field] == "yes" for field in (
                    "emergent_curriculum", "co_learning", "documented_learning_future_planning"
                )
            )
            record["derived_result"] = (
                "positive" if record["positive"]
                else "not_positive" if record["complete"]
                else "incomplete"
            )
            records.append(record)

        complete_flag = bool(payload.get("completed", payload.get("complete", False)))
        all_complete = all(record["complete"] for record in records)
        if complete_flag and not all_complete:
            return jsonify({"status": "error", "message": "Complete all ten PQI 3 records before completing"}), 400

        score = calculate_pqi3_score(records)
        stored_records = {f"record {index}": record for index, record in enumerate(records, start=1)}
        try:
            normalized_assessment_id = int(assessment_id)
            update_assessment_json_fields(
                normalized_assessment_id,
                pqi_findings={
                    "pqi3": {
                        "completed": complete_flag and all_complete,
                        **stored_records,
                    }
                },
            )
        except (TypeError, ValueError) as error:
            return jsonify({"status": "error", "message": str(error)}), 400

        set_current_assessment(normalized_assessment_id)
        return jsonify({
            "status": "success",
            "assessment_id": normalized_assessment_id,
            "completed": complete_flag and all_complete,
            "score": score,
        })

    @app.route("/api/assessments/pqi6", methods=["POST"])
    def save_pqi6():
        payload = request.get_json(silent=True) or {}
        assessment_id = payload.get("assessment_id") or get_current_assessment()
        if assessment_id is None:
            return jsonify({"status": "error", "message": "No assessment selected, unable to save"}), 400
        assessment_row = get_assessment_row_by_id(int(assessment_id))
        if assessment_row is None or not build_pqi_access_context(assessment_row)["pqi_allowed"]["6"]:
            return jsonify({"status": "error", "message": "PQI 6 is not available for this facility type"}), 400

        raw_responses = payload.get("responses")
        if not isinstance(raw_responses, dict):
            return jsonify({"status": "error", "message": "responses must be an object"}), 400

        normalized_responses: dict[str, list[bool]] = {}
        calculated_level = 1
        previous_level_complete = True
        for level_number, criteria in enumerate(PQI6_HIERARCHY.values(), start=1):
            raw_level_responses = raw_responses.get(str(level_number), [])
            raw_level_responses = raw_level_responses if isinstance(raw_level_responses, list) else []
            responses = [
                bool(raw_level_responses[index]) if index < len(raw_level_responses) and previous_level_complete else False
                for index in range(len(criteria))
            ]
            if level_number > 1:
                normalized_responses[str(level_number)] = responses
            level_complete = all(responses)
            if previous_level_complete and level_complete:
                calculated_level = level_number
            previous_level_complete = previous_level_complete and level_complete

        score_modifier = calculate_pqi6_score_modifier(calculated_level, normalized_responses)
        partial_descriptor = str(payload.get("partial_descriptor", "") or "").strip()
        observation_notes = str(payload.get("observation_notes", "") or "").strip()
        complete_flag = bool(payload.get("complete", False))
        try:
            normalized_assessment_id = int(assessment_id)
            update_assessment_json_fields(
                normalized_assessment_id,
                pqi_findings={
                    "pqi6": {
                        "complete": complete_flag,
                        "score": calculated_level,
                        "score_modifier": score_modifier,
                        "responses": normalized_responses,
                        "calculated_level": calculated_level,
                        "partial_descriptor": partial_descriptor,
                        "observation_notes": observation_notes,
                    }
                },
            )
        except (TypeError, ValueError) as error:
            return jsonify({"status": "error", "message": str(error)}), 400

        set_current_assessment(normalized_assessment_id)
        return jsonify(
            {
                "status": "success",
                "assessment_id": normalized_assessment_id,
                "complete": complete_flag,
                "score": calculated_level,
                "score_modifier": score_modifier,
                "calculated_level": calculated_level,
            }
        )

    @app.route("/api/assessments/pqi7", methods=["POST"])
    def save_pqi7():
        payload = request.get_json(silent=True) or {}
        assessment_id = payload.get("assessment_id") or get_current_assessment()
        if assessment_id is None:
            return jsonify({"status": "error", "message": "No assessment selected, unable to save"}), 400
        assessment_row = get_assessment_row_by_id(int(assessment_id))
        if assessment_row is None or not build_pqi_access_context(assessment_row)["pqi_allowed"]["7"]:
            return jsonify({"status": "error", "message": "PQI 7 is not available for this facility type"}), 400

        raw_responses = payload.get("responses")
        if not isinstance(raw_responses, dict):
            return jsonify({"status": "error", "message": "responses must be an object"}), 400

        normalized_responses: dict[str, list[bool]] = {}
        calculated_level = 1
        previous_level_complete = True
        for level_number, criteria in enumerate(PQI7_HIERARCHY.values(), start=1):
            raw_level_responses = raw_responses.get(str(level_number), [])
            raw_level_responses = raw_level_responses if isinstance(raw_level_responses, list) else []
            responses = [
                bool(raw_level_responses[index]) if index < len(raw_level_responses) and previous_level_complete else False
                for index in range(len(criteria))
            ]
            if level_number > 1:
                normalized_responses[str(level_number)] = responses
            level_complete = all(responses)
            if previous_level_complete and level_complete:
                calculated_level = level_number
            previous_level_complete = previous_level_complete and level_complete

        score_modifier = calculate_pqi7_score_modifier(calculated_level, normalized_responses)
        partial_descriptor = str(payload.get("partial_descriptor", "") or "").strip()
        observation_notes = str(payload.get("observation_notes", "") or "").strip()
        complete_flag = bool(payload.get("complete", False))
        try:
            normalized_assessment_id = int(assessment_id)
            update_assessment_json_fields(
                normalized_assessment_id,
                pqi_findings={
                    "pqi7": {
                        "complete": complete_flag,
                        "score": calculated_level,
                        "score_modifier": score_modifier,
                        "responses": normalized_responses,
                        "calculated_level": calculated_level,
                        "partial_descriptor": partial_descriptor,
                        "observation_notes": observation_notes,
                    }
                },
            )
        except (TypeError, ValueError) as error:
            return jsonify({"status": "error", "message": str(error)}), 400

        set_current_assessment(normalized_assessment_id)
        return jsonify(
            {
                "status": "success",
                "assessment_id": normalized_assessment_id,
                "complete": complete_flag,
                "score": calculated_level,
                "score_modifier": score_modifier,
                "calculated_level": calculated_level,
            }
        )

    @app.route("/api/assessments/pqi8", methods=["POST"])
    def save_pqi8():
        payload = request.get_json(silent=True) or {}
        assessment_id = payload.get("assessment_id") or get_current_assessment()
        if assessment_id is None:
            return jsonify({"status": "error", "message": "No assessment selected, unable to save"}), 400
        assessment_row = get_assessment_row_by_id(int(assessment_id))
        if assessment_row is None or not build_pqi_access_context(assessment_row)["pqi_allowed"]["8"]:
            return jsonify({"status": "error", "message": "PQI 8 is not available for this facility type"}), 400

        raw_responses = payload.get("responses")
        if not isinstance(raw_responses, dict):
            return jsonify({"status": "error", "message": "responses must be an object"}), 400

        normalized_responses: dict[str, list[bool]] = {}
        calculated_level = 1
        previous_level_complete = True
        for level_number, criteria in enumerate(PQI8_HIERARCHY.values(), start=1):
            raw_level_responses = raw_responses.get(str(level_number), [])
            raw_level_responses = raw_level_responses if isinstance(raw_level_responses, list) else []
            responses = [
                bool(raw_level_responses[index]) if index < len(raw_level_responses) and previous_level_complete else False
                for index in range(len(criteria))
            ]
            if level_number > 1:
                normalized_responses[str(level_number)] = responses
            level_complete = all(responses)
            if previous_level_complete and level_complete:
                calculated_level = level_number
            previous_level_complete = previous_level_complete and level_complete

        score_modifier = calculate_pqi8_score_modifier(calculated_level, normalized_responses)
        partial_descriptor = str(payload.get("partial_descriptor", "") or "").strip()
        observation_notes = str(payload.get("observation_notes", "") or "").strip()
        complete_flag = bool(payload.get("complete", False))
        try:
            normalized_assessment_id = int(assessment_id)
            update_assessment_json_fields(
                normalized_assessment_id,
                pqi_findings={
                    "pqi8": {
                        "complete": complete_flag,
                        "score": calculated_level,
                        "score_modifier": score_modifier,
                        "responses": normalized_responses,
                        "calculated_level": calculated_level,
                        "partial_descriptor": partial_descriptor,
                        "observation_notes": observation_notes,
                    }
                },
            )
        except (TypeError, ValueError) as error:
            return jsonify({"status": "error", "message": str(error)}), 400

        set_current_assessment(normalized_assessment_id)
        return jsonify(
            {
                "status": "success",
                "assessment_id": normalized_assessment_id,
                "complete": complete_flag,
                "score": calculated_level,
                "score_modifier": score_modifier,
                "calculated_level": calculated_level,
            }
        )

    @app.route("/api/assessments/pqi9", methods=["POST"])
    def save_pqi9():
        payload = request.get_json(silent=True) or {}
        assessment_id = payload.get("assessment_id") or get_current_assessment()
        if assessment_id is None:
            return jsonify({"status": "error", "message": "No assessment selected, unable to save"}), 400

        raw_responses = payload.get("responses")
        if not isinstance(raw_responses, dict):
            return jsonify({"status": "error", "message": "responses must be an object"}), 400

        raw_notes = payload.get("notes", {})
        if not isinstance(raw_notes, dict):
            return jsonify({"status": "error", "message": "notes must be an object"}), 400

        normalized_responses: dict[str, int] = {}
        normalized_notes: dict[str, str] = {}
        for observation_number in range(1, 11):
            raw_value = raw_responses.get(str(observation_number), raw_responses.get(observation_number))
            if raw_value in (None, ""):
                pass
            else:
                try:
                    score = int(raw_value)
                except (TypeError, ValueError):
                    return jsonify({"status": "error", "message": "PQI 9 observation scores must be integers between 1 and 4"}), 400

                if score not in (1, 2, 3, 4):
                    return jsonify({"status": "error", "message": "PQI 9 observation scores must be between 1 and 4"}), 400

                normalized_responses[str(observation_number)] = score

            raw_note = raw_notes.get(str(observation_number), raw_notes.get(observation_number, ""))
            normalized_notes[str(observation_number)] = str(raw_note or "").strip()

        complete_flag = bool(payload.get("complete", False))
        if complete_flag and len(normalized_responses) != 10:
            return jsonify({"status": "error", "message": "Complete all ten PQI 9 observations before completing"}), 400

        average_score = round(sum(normalized_responses.values()) / len(normalized_responses)) if normalized_responses else None

        try:
            normalized_assessment_id = int(assessment_id)
            update_assessment_json_fields(
                normalized_assessment_id,
                pqi_findings={
                    "pqi9": {
                        "complete": complete_flag,
                        "score": average_score,
                        "responses": normalized_responses,
                        "notes": normalized_notes,
                    }
                },
            )
        except (TypeError, ValueError) as error:
            return jsonify({"status": "error", "message": str(error)}), 400

        set_current_assessment(normalized_assessment_id)
        return jsonify(
            {
                "status": "success",
                "message": "PQI 9 saved successfully!",
                "assessment_id": normalized_assessment_id,
                "complete": complete_flag,
                "score": average_score,
            }
        )

    @app.route("/api/assessments/pqi10", methods=["POST"])
    def save_pqi10():
        payload = request.get_json(silent=True) or {}
        assessment_id = payload.get("assessment_id") or get_current_assessment()
        if assessment_id is None:
            return jsonify({"status": "error", "message": "No assessment selected, unable to save"}), 400

        raw_responses = payload.get("responses")
        if not isinstance(raw_responses, dict):
            return jsonify({"status": "error", "message": "responses must be an object"}), 400

        raw_notes = payload.get("notes", {})
        if not isinstance(raw_notes, dict):
            return jsonify({"status": "error", "message": "notes must be an object"}), 400

        normalized_responses: dict[str, int] = {}
        normalized_notes: dict[str, str] = {}
        for observation_number in range(1, PQI10_OBSERVATION_COUNT + 1):
            raw_value = raw_responses.get(str(observation_number), raw_responses.get(observation_number))
            if raw_value not in (None, ""):
                try:
                    score = int(raw_value)
                except (TypeError, ValueError):
                    return jsonify({"status": "error", "message": "PQI 10 observation scores must be integers between 1 and 4"}), 400
                if score not in PQI10_LIKERT_SCORE_RANGE:
                    return jsonify({"status": "error", "message": "PQI 10 observation scores must be between 1 and 4"}), 400
                normalized_responses[str(observation_number)] = score

            raw_note = raw_notes.get(str(observation_number), raw_notes.get(observation_number, ""))
            normalized_notes[str(observation_number)] = str(raw_note or "").strip()

        complete_flag = bool(payload.get("complete", False))
        if complete_flag and len(normalized_responses) != PQI10_OBSERVATION_COUNT:
            return jsonify({"status": "error", "message": "Complete all ten PQI 10 observations before completing"}), 400

        average_score = round(sum(normalized_responses.values()) / len(normalized_responses)) if normalized_responses else None
        try:
            normalized_assessment_id = int(assessment_id)
            update_assessment_json_fields(
                normalized_assessment_id,
                pqi_findings={
                    "pqi10": {
                        "complete": complete_flag,
                        "score": average_score,
                        "responses": normalized_responses,
                        "notes": normalized_notes,
                    }
                },
            )
        except (TypeError, ValueError) as error:
            return jsonify({"status": "error", "message": str(error)}), 400

        set_current_assessment(normalized_assessment_id)
        return jsonify({"status": "success", "message": "PQI 10 saved successfully!", "assessment_id": normalized_assessment_id, "complete": complete_flag, "score": average_score})

    @app.route("/api/assessments/pqi4", methods=["POST"])
    def save_pqi4():
        payload = request.get_json(silent=True) or {}
        assessment_id = payload.get("assessment_id") or get_current_assessment()
        if assessment_id is None:
            return jsonify({"status": "error", "message": "No assessment selected, unable to save"}), 400

        responses = payload.get("responses")
        if not isinstance(responses, dict):
            return jsonify({"status": "error", "message": "responses must be an object"}), 400

        optional_note = str(payload.get("optional_note", "") or "").strip()
        complete_flag = bool(payload.get("complete", False))
        question_ids = [str(index) for index in range(1, len(PQI4_STAFF_FAMILY_OPPORTUNITIES_QUESTIONS) + 1)]
        normalized_responses = {
            question_id: normalize_yes_no(responses.get(question_id, responses.get(f"4.{question_id}")))
            for question_id in question_ids
        }
        all_answered = all(value in {"yes", "no"} for value in normalized_responses.values())
        if complete_flag and not all_answered:
            return jsonify({"status": "error", "message": "Answer all PQI 4 questions before completing"}), 400

        ordered_responses = [normalized_responses[question_id] for question_id in question_ids]
        score = calculate_pqi4_score(ordered_responses)
        yes_count = sum(value == "yes" for value in ordered_responses)
        stored_responses = {f"4.{question_id}": normalized_responses[question_id] for question_id in question_ids}

        try:
            normalized_assessment_id = int(assessment_id)
            update_assessment_json_fields(
                normalized_assessment_id,
                pqi_findings={
                    "pqi4": {
                        "complete": complete_flag,
                        "score": score,
                        "question_count": len(question_ids),
                        "yes_count": yes_count,
                        "responses": stored_responses,
                        "optional_note": optional_note,
                    }
                },
            )
        except (TypeError, ValueError) as error:
            return jsonify({"status": "error", "message": str(error)}), 400

        set_current_assessment(normalized_assessment_id)
        return jsonify(
            {
                "status": "success",
                "message": "PQI 4 saved successfully!",
                "assessment_id": normalized_assessment_id,
                "complete": complete_flag,
                "score": score,
                "yes_count": yes_count,
                "question_count": len(question_ids),
            }
        )

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
                existing_status = str(current_assessment_row["status"] or "not available").strip() or "not available"
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

    @app.route("/api/assessments/import-input-snapshot", methods=["POST"])
    def import_input_snapshot():
        uploaded_file = request.files.get("snapshot")
        if uploaded_file is None or not uploaded_file.filename:
            return jsonify({"status": "error", "message": "Choose a JSON snapshot file to import"}), 400

        try:
            snapshot = json.loads(uploaded_file.read().decode("utf-8-sig"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return jsonify({"status": "error", "message": "The selected file is not valid JSON"}), 400

        snapshots = snapshot if isinstance(snapshot, list) else [snapshot]
        if not snapshots or not all(isinstance(item, dict) for item in snapshots):
            return jsonify({"status": "error", "message": "The file must contain an assessment object or an array of assessment objects"}), 400

        try:
            assessment_ids = [import_assessment_input_snapshot(item) for item in snapshots]
        except (TypeError, ValueError) as error:
            return jsonify({"status": "error", "message": str(error)}), 400

        assessment_id = assessment_ids[-1]
        set_current_assessment(assessment_id)
        return jsonify({"status": "success", "assessment_id": assessment_id, "assessment_ids": assessment_ids, "imported_count": len(assessment_ids), "next_screen": url_for("screen", screen_id="assessment-list")})
