import json
from datetime import datetime

from flask import request, url_for
from markupsafe import Markup, escape

from constants import (
    ASSESSMENTS_PER_PAGE,
    CALCULATION_MODEL,
    CALCULATION_MODEL_PUBLICATION_DATE,
    CALCULATION_MODEL_VERSION,
    CALCULATION_MODEL_PUBLICATION_DATE,
    FACILITY_TYPE_OPTIONS,
    DEFAULT_INSPECTOR_NAME,
    DEFAULT_ASSESSMENT_FORM_VALUES,
    DEFAULT_FACILITY_IDENTIFICATION_FORM_VALUES,
    FACILITY_TYPE_PQI_MAPPING,
    INCLUDED_COMPONENTS,
    NON_PQI_FIELD_REQUIREDNESS,
    PQI2_ENVIRONMENT_QUESTIONS,
    PQI4_BAND_MAPPING,
    PQI4_STAFF_FAMILY_OPPORTUNITIES_QUESTIONS,
    PQI5_CHILD_PROGRESS_QUESTIONS,
    PQI5_QUESTION_POINTS,
    PQI3_RECORD_COUNT,
    PQI6_HIERARCHY,
    PQI7_HIERARCHY,
    PQI8_HIERARCHY,
    PQI9_LIKERT_SCORE_RANGE,
    PQI9_OBSERVATION_COUNT,
    PQI9_OBSERVATION_DURATION_SECONDS,
    PQI10_LIKERT_SCORE_RANGE,
    PQI10_OBSERVATION_COUNT,
    PQI10_OBSERVATION_DURATION_SECONDS,
    REGULATION_EFFECTIVE_DATE,
    REGULATION_SET_NAME,
    REGULATION_SET_VERSION,
    STRUCTURAL_REFERENCE_TABLE,
    THRESHOLD_SET,
    WORKFLOW_PROGRESS_BY_STATUS,
    PROGRAM_QUALITY_OUTCOMES,
)
from repositories.assessments import (
    get_assessment_row_by_id,
    get_dashboard_counts_and_recent,
    get_duplicate_candidate_rows,
    get_most_recent_assessment_row,
    query_assessment_list,
)
from services.formatters import (
    calculate_pqi1_score,
    calculate_pqi2_score,
    calculate_pqi3_score,
    calculate_pqi4_score,
    calculate_pqi5_points,
    calculate_pqi6_score_modifier,
    format_date_label,
    format_pqi6_score,
    calculate_pqi7_score_modifier,
    format_pqi7_score,
    calculate_pqi8_score_modifier,
    format_pqi8_score,
    format_timestamp_label,
    get_status_chip_class,
    names_are_similar,
    normalize_yes_no,
    normalize_text,
    round_percentage_half_up,
)
from session_state import get_current_assessment


def get_current_assessment_row() -> dict | None:
    assessment_id = get_current_assessment()
    if assessment_id is None:
        return None
    return get_assessment_row_by_id(int(assessment_id))


def get_assessment_label(assessment_row: dict | object | None = None, *, assessment_id: int | None = None) -> str:
    if assessment_row is not None:
        try:
            assessment_id = assessment_row["id"]
        except (KeyError, TypeError):
            if hasattr(assessment_row, "get"):
                assessment_id = assessment_row.get("id")
            else:
                assessment_id = None

    if assessment_id is None:
        return "No assessment selected"

    return f"Assessment ASMT-{int(assessment_id):05d}"


def _load_json_object(raw_value: object, default: dict) -> dict:
    if isinstance(raw_value, dict):
        return raw_value

    if raw_value is None:
        return dict(default)

    cleaned_value = str(raw_value).strip()
    if not cleaned_value:
        return dict(default)

    try:
        parsed_value = json.loads(cleaned_value)
    except json.JSONDecodeError:
        return dict(default)

    return parsed_value if isinstance(parsed_value, dict) else dict(default)


def _build_pqi3_records(raw_entry: object) -> list[dict]:
    entry = raw_entry if isinstance(raw_entry, dict) else {}
    raw_records = entry.get("records", entry)
    records = []
    for index in range(1, PQI3_RECORD_COUNT + 1):
        raw_record = {}
        if isinstance(raw_records, dict):
            for candidate_key in (f"record {index}", str(index), index):
                if candidate_key in raw_records:
                    raw_record = raw_records[candidate_key]
                    break
        raw_record = raw_record if isinstance(raw_record, dict) else {}
        values = {
            "emergent_curriculum": normalize_yes_no(raw_record.get("emergent_curriculum")),
            "co_learning": normalize_yes_no(raw_record.get("co_learning")),
            "documented_learning_future_planning": normalize_yes_no(
                raw_record.get("documented_learning_future_planning", raw_record.get("documentation"))
            ),
        }
        values["complete"] = all(value in {"yes", "no"} for value in values.values())
        values["positive"] = values["complete"] and all(value == "yes" for value in values.values())
        values["notes"] = str(raw_record.get("notes", "") or "").strip()
        records.append(values)
    return records


def _build_pqi68_card(pqi_number: int, entry: object, hierarchy: dict) -> dict:
    entry = entry if isinstance(entry, dict) else {}
    raw_responses = entry.get("responses", {})
    raw_responses = raw_responses if isinstance(raw_responses, dict) else {}
    score = 0
    has_input = False

    for level_number, (level_name, criteria) in enumerate(hierarchy.items(), start=1):
        raw_level = raw_responses.get(str(level_number), raw_responses.get(level_name, []))
        raw_level = raw_level if isinstance(raw_level, list) else []
        checked_count = sum(bool(value) for value in raw_level[: len(criteria)])
        has_input = has_input or checked_count > 0
        if checked_count == len(criteria):
            score = level_number
        else:
            break

    has_input = has_input or bool(str(entry.get("partial_descriptor", "") or "").strip())
    has_input = has_input or bool(str(entry.get("observation_notes", "") or "").strip())
    has_input = has_input or bool(entry.get("score"))
    complete = bool(entry.get("complete", False))
    status = "complete" if complete else "draft" if has_input else "empty"
    return {
        "number": pqi_number,
        "status": status,
        "status_label": status.title(),
        "score": score if score else "--",
    }


def _build_pqi910_card(pqi_number: int, entry: object, observation_count: int) -> dict:
    entry = entry if isinstance(entry, dict) else {}
    responses = entry.get("responses", {})
    responses = responses if isinstance(responses, dict) else {}
    notes = entry.get("notes", {})
    notes = notes if isinstance(notes, dict) else {}
    completed_count = sum(value not in (None, "") for value in responses.values())
    has_input = bool(responses) or any(str(value or "").strip() for value in notes.values())
    complete = bool(entry.get("complete", False))
    status = "complete" if complete else "draft" if has_input else "empty"
    score = entry.get("score")
    try:
        score = int(score) if score not in (None, "") else None
    except (TypeError, ValueError):
        score = None
    return {
        "number": pqi_number,
        "status": status,
        "status_label": status.title(),
        "score": score if score is not None else "--",
        "completed_count": min(completed_count, observation_count),
        "observation_count": observation_count,
    }


def build_pqi3_context(preview: bool = False) -> dict:
    assessment_row = get_current_assessment_row()
    assessment_id = assessment_row["id"] if assessment_row is not None else None
    assessment_code = f"ASMT-{assessment_id:05d}" if assessment_id is not None else "No assessment selected"
    assessment_label = get_assessment_label(assessment_row)
    pqi_findings = _load_json_object(assessment_row["pqi_findings"], {}) if assessment_row is not None else {}
    pqi3_entry = pqi_findings.get("pqi3", {}) if isinstance(pqi_findings, dict) else {}
    records = _build_pqi3_records(pqi3_entry)
    completed_count = sum(1 for record in records if record["complete"])
    positive_count = sum(1 for record in records if record["positive"])
    complete = completed_count == PQI3_RECORD_COUNT
    percentage = round_percentage_half_up((positive_count / PQI3_RECORD_COUNT) * 100)
    score = calculate_pqi3_score(records)
    return {
        "assessment_code": assessment_code,
        "assessment_label": assessment_label,
        "editing_assessment_id": assessment_id,
        "pqi3_records": records[:4] if preview else records,
        "pqi3_preview": preview,
        "pqi3_complete": bool(pqi3_entry.get("completed", pqi3_entry.get("complete", False))),
        "pqi3_completed_count": completed_count,
        "pqi3_positive_count": positive_count,
        "pqi3_percentage": percentage,
        "pqi3_score": score,
        "pqi3_save_url": url_for("save_pqi3"),
        "pqi3_full_href": url_for("screen", screen_id="pqi3"),
        "pqi3_back_href": url_for("screen", screen_id="pqi-findings-entry"),
    }


def build_pqi910_context() -> dict:
    assessment_row = get_current_assessment_row()
    assessment_id = assessment_row["id"] if assessment_row is not None else None
    assessment_label = get_assessment_label(assessment_row)
    pqi_findings = _load_json_object(assessment_row["pqi_findings"], {}) if assessment_row is not None else {}
    def build_entry(pqi_key: str, observation_count: int, likert_scores: tuple[int, ...]) -> tuple[dict, dict, bool]:
        entry = pqi_findings.get(pqi_key, {}) if isinstance(pqi_findings, dict) else {}
        entry = entry if isinstance(entry, dict) else {}
        raw_responses = entry.get("responses", {})
        raw_responses = raw_responses if isinstance(raw_responses, dict) else {}
        saved_scores = {}
        for observation_number in range(1, observation_count + 1):
            raw_value = raw_responses.get(str(observation_number), raw_responses.get(observation_number))
            if raw_value in (None, ""):
                continue
            try:
                score = int(raw_value)
            except (TypeError, ValueError):
                continue
            if score in likert_scores:
                saved_scores[str(observation_number)] = score

        raw_notes = entry.get("notes", {})
        raw_notes = raw_notes if isinstance(raw_notes, dict) else {}
        saved_notes = {
            str(observation_number): str(raw_notes.get(str(observation_number), raw_notes.get(observation_number, "")) or "").strip()
            for observation_number in range(1, observation_count + 1)
        }
        return saved_scores, saved_notes, bool(entry.get("complete", False))

    pqi9_scores, pqi9_notes, pqi9_complete = build_entry("pqi9", PQI9_OBSERVATION_COUNT, PQI9_LIKERT_SCORE_RANGE)
    pqi10_scores, pqi10_notes, pqi10_complete = build_entry("pqi10", PQI10_OBSERVATION_COUNT, PQI10_LIKERT_SCORE_RANGE)

    return {
        "assessment_label": assessment_label,
        "editing_assessment_id": assessment_id,
        "pqi910_observation_count": PQI9_OBSERVATION_COUNT,
        "pqi910_duration_seconds": PQI9_OBSERVATION_DURATION_SECONDS,
        "pqi910_likert_scores": PQI9_LIKERT_SCORE_RANGE,
        "pqi910_saved_scores": pqi9_scores,
        "pqi910_saved_notes": pqi9_notes,
        "pqi910_complete": pqi9_complete,
        "pqi910_save_url": url_for("save_pqi9"),
        "pqi10_observation_count": PQI10_OBSERVATION_COUNT,
        "pqi10_duration_seconds": PQI10_OBSERVATION_DURATION_SECONDS,
        "pqi10_likert_scores": PQI10_LIKERT_SCORE_RANGE,
        "pqi10_saved_scores": pqi10_scores,
        "pqi10_saved_notes": pqi10_notes,
        "pqi10_complete": pqi10_complete,
        "pqi10_save_url": url_for("save_pqi10"),
        "pqi910_back_href": url_for("screen", screen_id="pqi-findings-entry"),
    }


def build_pqi6_context() -> dict:
    assessment_row = get_current_assessment_row()
    assessment_id = assessment_row["id"] if assessment_row is not None else None
    assessment_label = get_assessment_label(assessment_row)
    pqi_findings = _load_json_object(assessment_row["pqi_findings"], {}) if assessment_row is not None else {}
    pqi6_entry = pqi_findings.get("pqi6", {}) if isinstance(pqi_findings, dict) else {}
    pqi6_entry = pqi6_entry if isinstance(pqi6_entry, dict) else {}
    raw_responses = pqi6_entry.get("responses", {})
    raw_responses = raw_responses if isinstance(raw_responses, dict) else {}

    levels = []
    highest_complete_level = 1
    previous_level_complete = True
    for level_number, (level_name, criteria) in enumerate(PQI6_HIERARCHY.items(), start=1):
        raw_level_responses = raw_responses.get(str(level_number), raw_responses.get(level_name, [])) if level_number > 1 else []
        raw_level_responses = raw_level_responses if isinstance(raw_level_responses, list) else []
        responses = [True for _ in criteria] if level_number == 1 else [
            bool(raw_level_responses[index]) if index < len(raw_level_responses) and previous_level_complete else False
            for index in range(len(criteria))
        ]
        met_count = sum(responses)
        is_complete = met_count == len(criteria)
        if level_number == 1:
            status = "baseline"
        elif not previous_level_complete:
            status = "locked"
        elif is_complete:
            status = "complete"
            highest_complete_level = level_number
        elif met_count:
            status = "partial"
        else:
            status = "empty"
        levels.append(
            {
                "number": level_number,
                "name": level_name,
                "criteria": [
                    {"text": criterion, "checked": responses[index]}
                    for index, criterion in enumerate(criteria)
                ],
                "criteria_count": len(criteria),
                "met_count": met_count,
                "status": status,
            }
        )
        previous_level_complete = previous_level_complete and is_complete

    score_modifier = calculate_pqi6_score_modifier(highest_complete_level, raw_responses)
    score_display = format_pqi6_score(highest_complete_level, score_modifier)

    return {
        "assessment_label": assessment_label,
        "editing_assessment_id": assessment_id,
        "pqi6_levels": levels,
        "pqi6_score": highest_complete_level,
        "pqi6_score_modifier": score_modifier,
        "pqi6_score_display": score_display,
        "pqi6_calculated_level": highest_complete_level,
        "pqi6_partial_descriptor": str(pqi6_entry.get("partial_descriptor", "") or "").strip(),
        "pqi6_observation_notes": str(pqi6_entry.get("observation_notes", "") or "").strip(),
        "pqi6_complete": bool(pqi6_entry.get("complete", False)),
        "pqi6_save_url": url_for("save_pqi6"),
        "pqi6_back_href": url_for("screen", screen_id="pqi-findings-entry"),
    }


def build_pqi7_context() -> dict:
    assessment_row = get_current_assessment_row()
    assessment_id = assessment_row["id"] if assessment_row is not None else None
    assessment_label = get_assessment_label(assessment_row)
    pqi_findings = _load_json_object(assessment_row["pqi_findings"], {}) if assessment_row is not None else {}
    pqi7_entry = pqi_findings.get("pqi7", {}) if isinstance(pqi_findings, dict) else {}
    pqi7_entry = pqi7_entry if isinstance(pqi7_entry, dict) else {}
    raw_responses = pqi7_entry.get("responses", {})
    raw_responses = raw_responses if isinstance(raw_responses, dict) else {}

    levels = []
    highest_complete_level = 1
    previous_level_complete = True
    for level_number, (level_name, criteria) in enumerate(PQI7_HIERARCHY.items(), start=1):
        raw_level_responses = raw_responses.get(str(level_number), raw_responses.get(level_name, [])) if level_number > 1 else []
        raw_level_responses = raw_level_responses if isinstance(raw_level_responses, list) else []
        responses = [True for _ in criteria] if level_number == 1 else [
            bool(raw_level_responses[index]) if index < len(raw_level_responses) and previous_level_complete else False
            for index in range(len(criteria))
        ]
        met_count = sum(responses)
        is_complete = met_count == len(criteria)
        if level_number == 1:
            status = "baseline"
        elif not previous_level_complete:
            status = "locked"
        elif is_complete:
            status = "complete"
            highest_complete_level = level_number
        elif met_count:
            status = "partial"
        else:
            status = "empty"
        levels.append({
            "number": level_number,
            "name": level_name,
            "criteria": [{"text": criterion, "checked": responses[index]} for index, criterion in enumerate(criteria)],
            "criteria_count": len(criteria),
            "met_count": met_count,
            "status": status,
        })
        previous_level_complete = previous_level_complete and is_complete

    score_modifier = calculate_pqi7_score_modifier(highest_complete_level, raw_responses)
    return {
        "assessment_label": assessment_label,
        "editing_assessment_id": assessment_id,
        "pqi7_levels": levels,
        "pqi7_score_display": format_pqi7_score(highest_complete_level, score_modifier),
        "pqi7_partial_descriptor": str(pqi7_entry.get("partial_descriptor", "") or "").strip(),
        "pqi7_observation_notes": str(pqi7_entry.get("observation_notes", "") or "").strip(),
        "pqi7_complete": bool(pqi7_entry.get("complete", False)),
        "pqi7_save_url": url_for("save_pqi7"),
        "pqi7_back_href": url_for("screen", screen_id="pqi6-8-hierarchy"),
    }


def build_pqi8_context() -> dict:
    assessment_row = get_current_assessment_row()
    assessment_id = assessment_row["id"] if assessment_row is not None else None
    assessment_label = get_assessment_label(assessment_row)
    pqi_findings = _load_json_object(assessment_row["pqi_findings"], {}) if assessment_row is not None else {}
    pqi8_entry = pqi_findings.get("pqi8", {}) if isinstance(pqi_findings, dict) else {}
    pqi8_entry = pqi8_entry if isinstance(pqi8_entry, dict) else {}
    raw_responses = pqi8_entry.get("responses", {})
    raw_responses = raw_responses if isinstance(raw_responses, dict) else {}

    levels = []
    highest_complete_level = 1
    previous_level_complete = True
    for level_number, (level_name, criteria) in enumerate(PQI8_HIERARCHY.items(), start=1):
        raw_level_responses = raw_responses.get(str(level_number), raw_responses.get(level_name, [])) if level_number > 1 else []
        raw_level_responses = raw_level_responses if isinstance(raw_level_responses, list) else []
        responses = [True for _ in criteria] if level_number == 1 else [
            bool(raw_level_responses[index]) if index < len(raw_level_responses) and previous_level_complete else False
            for index in range(len(criteria))
        ]
        met_count = sum(responses)
        is_complete = met_count == len(criteria)
        if level_number == 1:
            status = "baseline"
        elif not previous_level_complete:
            status = "locked"
        elif is_complete:
            status = "complete"
            highest_complete_level = level_number
        elif met_count:
            status = "partial"
        else:
            status = "empty"
        levels.append({
            "number": level_number,
            "name": level_name,
            "criteria": [{"text": criterion, "checked": responses[index]} for index, criterion in enumerate(criteria)],
            "criteria_count": len(criteria),
            "met_count": met_count,
            "status": status,
        })
        previous_level_complete = previous_level_complete and is_complete

    score_modifier = calculate_pqi8_score_modifier(highest_complete_level, raw_responses)
    return {
        "assessment_label": assessment_label,
        "editing_assessment_id": assessment_id,
        "pqi8_levels": levels,
        "pqi8_score_display": format_pqi8_score(highest_complete_level, score_modifier),
        "pqi8_partial_descriptor": str(pqi8_entry.get("partial_descriptor", "") or "").strip(),
        "pqi8_observation_notes": str(pqi8_entry.get("observation_notes", "") or "").strip(),
        "pqi8_complete": bool(pqi8_entry.get("complete", False)),
        "pqi8_save_url": url_for("save_pqi8"),
        "pqi8_back_href": url_for("screen", screen_id="pqi7"),
    }


def build_contact_hours_context() -> dict:
    assessment_row = get_current_assessment_row()

    contact_hours_form = {
        "to1": "",
        "to2": "",
        "ta": "",
        "nc": "",
        "th1": "",
        "th2": "",
        "density_model": "",
        "required_ratio": "",
        "ratio_source": "",
        "rwch_reference": "",
        "calculated_ch": "",
    }

    if assessment_row is not None:
        saved_contact_hours = _load_json_object(assessment_row["contact_hours"], {})
        for key in contact_hours_form:
            value = saved_contact_hours.get(key, "")
            contact_hours_form[key] = "" if value is None else str(value)

    assessment_id = assessment_row["id"] if assessment_row is not None else None
    assessment_code = f"ASMT-{assessment_id:05d}" if assessment_id is not None else "No assessment selected"
    assessment_label = get_assessment_label(assessment_row)

    return {
        "assessment_code": assessment_code,
        "assessment_label": assessment_label,
        "editing_assessment_id": assessment_id,
        "contact_hours_form": contact_hours_form,
        "save_indicator_label": f"Autosaved {format_timestamp_label(assessment_row['modified_at'])}" if assessment_row is not None else "Autosaved --",
    }


def build_pqi1_context() -> dict:
    assessment_row = get_current_assessment_row()

    pqi1_form = {
        "certified_teaching_staff": "",
        "total_teaching_staff": "",
    }
    assessment_id = None
    assessment_code = "No assessment selected"
    assessment_label = "No assessment selected"
    score = None
    pqi1_complete = False
    pqi2_form = {str(index): "" for index, _ in enumerate(PQI2_ENVIRONMENT_QUESTIONS, start=1)}
    pqi2_complete = False
    pqi2_score = None
    pqi2_optional_note = ""
    pqi4_form = {str(index): "" for index, _ in enumerate(PQI4_STAFF_FAMILY_OPPORTUNITIES_QUESTIONS, start=1)}
    pqi4_complete = False
    pqi4_score = None
    pqi4_optional_note = ""
    pqi5_form = {str(index): "" for index, _ in enumerate(PQI5_CHILD_PROGRESS_QUESTIONS, start=1)}
    pqi5_complete = False
    pqi5_base_points = None
    pqi5_bonus_point = None
    pqi5_score = None
    pqi68_cards = [
        _build_pqi68_card(6, {}, PQI6_HIERARCHY),
        _build_pqi68_card(7, {}, PQI7_HIERARCHY),
        _build_pqi68_card(8, {}, PQI8_HIERARCHY),
    ]
    pqi68_complete_count = 0
    pqi910_cards = [
        _build_pqi910_card(9, {}, PQI9_OBSERVATION_COUNT),
        _build_pqi910_card(10, {}, PQI10_OBSERVATION_COUNT),
    ]
    pqi910_complete_count = 0

    if assessment_row is not None:
        assessment_id = assessment_row["id"]
        assessment_code = f"ASMT-{assessment_id:05d}" if assessment_id is not None else assessment_code
        assessment_label = get_assessment_label(assessment_row)

        pqi_findings = _load_json_object(assessment_row["pqi_findings"], {})
        pqi68_cards = [
            _build_pqi68_card(6, pqi_findings.get("pqi6"), PQI6_HIERARCHY),
            _build_pqi68_card(7, pqi_findings.get("pqi7"), PQI7_HIERARCHY),
            _build_pqi68_card(8, pqi_findings.get("pqi8"), PQI8_HIERARCHY),
        ]
        pqi68_complete_count = sum(card["status"] == "complete" for card in pqi68_cards)
        pqi910_cards = [
            _build_pqi910_card(9, pqi_findings.get("pqi9"), PQI9_OBSERVATION_COUNT),
            _build_pqi910_card(10, pqi_findings.get("pqi10"), PQI10_OBSERVATION_COUNT),
        ]
        pqi910_complete_count = sum(card["status"] == "complete" for card in pqi910_cards)
        pqi1_entry = pqi_findings.get("pqi1") if isinstance(pqi_findings, dict) else {}
        if isinstance(pqi1_entry, dict):
            pqi1_complete = bool(pqi1_entry.get("complete", False))
            pqi1_form.update(
                {
                    "certified_teaching_staff": str(pqi1_entry.get("certified_teaching_staff", "")).strip(),
                    "total_teaching_staff": str(pqi1_entry.get("total_teaching_staff", "")).strip(),
                }
            )
        score = calculate_pqi1_score(pqi1_form["certified_teaching_staff"], pqi1_form["total_teaching_staff"])

        pqi2_entry = pqi_findings.get("pqi2") if isinstance(pqi_findings, dict) else {}
        if isinstance(pqi2_entry, dict):
            responses = pqi2_entry.get("responses")
            if isinstance(responses, dict):
                normalized_by_legacy_key: dict[str, str | None] = {}
                for raw_key, raw_value in responses.items():
                    if not isinstance(raw_key, str):
                        continue
                    key_text = raw_key.strip()
                    if key_text in {str(index) for index, _ in enumerate(PQI2_ENVIRONMENT_QUESTIONS, start=1)}:
                        normalized_by_legacy_key[key_text] = normalize_yes_no(raw_value)
                        continue
                    if "." in key_text:
                        suffix = key_text.rsplit(".", 1)[-1]
                        if suffix.isdigit():
                            normalized_index = str(int(suffix))
                            if normalized_index in {str(index) for index, _ in enumerate(PQI2_ENVIRONMENT_QUESTIONS, start=1)}:
                                normalized_by_legacy_key[normalized_index] = normalize_yes_no(raw_value)

                for index, _ in enumerate(PQI2_ENVIRONMENT_QUESTIONS, start=1):
                    key = str(index)
                    raw_value = responses.get(key)
                    if raw_value is None:
                        raw_value = normalized_by_legacy_key.get(key)
                    normalized_value = normalize_yes_no(raw_value)
                    pqi2_form[key] = normalized_value or ""

            pqi2_complete = bool(pqi2_entry.get("complete", False))
            pqi2_score = calculate_pqi2_score([pqi2_form[str(index)] for index, _ in enumerate(PQI2_ENVIRONMENT_QUESTIONS, start=1)])

        pqi2_optional_note = str((pqi_findings.get("pqi2") if isinstance(pqi_findings, dict) else {}).get("optional_note", "") or "").strip() if isinstance(pqi_findings, dict) and isinstance(pqi_findings.get("pqi2"), dict) else ""

        pqi4_entry = pqi_findings.get("pqi4") if isinstance(pqi_findings, dict) else {}
        if isinstance(pqi4_entry, dict):
            responses = pqi4_entry.get("responses")
            if isinstance(responses, dict):
                for index, _ in enumerate(PQI4_STAFF_FAMILY_OPPORTUNITIES_QUESTIONS, start=1):
                    key = str(index)
                    raw_value = responses.get(key, responses.get(f"4.{key}"))
                    pqi4_form[key] = normalize_yes_no(raw_value) or ""

            pqi4_complete = bool(pqi4_entry.get("complete", False))
            pqi4_score = calculate_pqi4_score([pqi4_form[str(index)] for index, _ in enumerate(PQI4_STAFF_FAMILY_OPPORTUNITIES_QUESTIONS, start=1)])

        pqi4_optional_note = str((pqi_findings.get("pqi4") if isinstance(pqi_findings, dict) else {}).get("optional_note", "") or "").strip() if isinstance(pqi_findings, dict) and isinstance(pqi_findings.get("pqi4"), dict) else ""

        pqi5_entry = pqi_findings.get("pqi5") if isinstance(pqi_findings, dict) else {}
        if isinstance(pqi5_entry, dict):
            responses = pqi5_entry.get("responses")
            if isinstance(responses, dict):
                for index, _ in enumerate(PQI5_CHILD_PROGRESS_QUESTIONS, start=1):
                    key = str(index)
                    raw_value = responses.get(key, responses.get(f"5.{key}"))
                    pqi5_form[key] = normalize_yes_no(raw_value) or ""

            pqi5_complete = bool(pqi5_entry.get("complete", False))
            pqi5_points = calculate_pqi5_points([pqi5_form[str(index)] for index, _ in enumerate(PQI5_CHILD_PROGRESS_QUESTIONS, start=1)])
            if pqi5_points is not None:
                pqi5_base_points, pqi5_bonus_point, pqi5_score = pqi5_points

    pqi2_question_count = len(PQI2_ENVIRONMENT_QUESTIONS)
    pqi2_completed_count = sum(1 for value in pqi2_form.values() if value in {"yes", "no"})
    pqi2_yes_count = sum(1 for value in pqi2_form.values() if value == "yes")
    pqi2_all_answered = pqi2_completed_count == pqi2_question_count
    pqi2_percentage = round_percentage_half_up((pqi2_yes_count / pqi2_question_count) * 100) if pqi2_all_answered else None
    pqi2_score_label = f"Score {pqi2_score}" if pqi2_score is not None else f"{pqi2_completed_count} of {pqi2_question_count} answered"
    pqi4_question_count = len(PQI4_STAFF_FAMILY_OPPORTUNITIES_QUESTIONS)
    pqi4_completed_count = sum(1 for value in pqi4_form.values() if value in {"yes", "no"})
    pqi4_yes_count = sum(1 for value in pqi4_form.values() if value == "yes")
    pqi4_all_answered = pqi4_completed_count == pqi4_question_count
    pqi4_percentage = round_percentage_half_up((pqi4_yes_count / pqi4_question_count) * 100) if pqi4_all_answered else None
    pqi4_score_label = f"Score {pqi4_score}" if pqi4_score is not None else f"{pqi4_completed_count} of {pqi4_question_count} answered"

    pqi5_question_count = len(PQI5_CHILD_PROGRESS_QUESTIONS)
    pqi5_completed_count = sum(1 for value in pqi5_form.values() if value in {"yes", "no"})
    pqi5_score_label = f"Score {pqi5_score}" if pqi5_score is not None else f"{pqi5_completed_count} of {pqi5_question_count} answered"

    pqi3_context = build_pqi3_context()
    pqi_allowed = build_pqi_access_context(assessment_row)["pqi_allowed"]
    pqi_progress_units = {
        "1": (sum(value != "" for value in pqi1_form.values()), 2),
        "2": (pqi2_completed_count, pqi2_question_count),
        "3": (pqi3_context["pqi3_completed_count"], PQI3_RECORD_COUNT),
        "4": (pqi4_completed_count, pqi4_question_count),
        "5": (pqi5_completed_count, pqi5_question_count),
        "6": (int(any(card["number"] == 6 and card["status"] == "complete" for card in pqi68_cards)), 1),
        "7": (int(any(card["number"] == 7 and card["status"] == "complete" for card in pqi68_cards)), 1),
        "8": (int(any(card["number"] == 8 and card["status"] == "complete" for card in pqi68_cards)), 1),
        "9": (next(card["completed_count"] for card in pqi910_cards if card["number"] == 9), PQI9_OBSERVATION_COUNT),
        "10": (next(card["completed_count"] for card in pqi910_cards if card["number"] == 10), PQI10_OBSERVATION_COUNT),
    }
    pqi_progress_numerator = sum(completed for number, (completed, _) in pqi_progress_units.items() if pqi_allowed[number])
    pqi_progress_denominator = sum(total for number, (_, total) in pqi_progress_units.items() if pqi_allowed[number])
    pqi_progress_percentage = round_percentage_half_up((pqi_progress_numerator / pqi_progress_denominator) * 100) if pqi_progress_denominator else 0

    return {
        "assessment_code": assessment_code,
        "assessment_label": assessment_label,
        "editing_assessment_id": assessment_id,
        "pqi1_form": pqi1_form,
        "pqi1_score": score,
        "pqi1_complete": pqi1_complete,
        "pqi1_score_label": f"Score {score}" if score is not None else "Not started",
        "pqi1_save_url": url_for("save_pqi1"),
        "pqi1_back_href": url_for("screen", screen_id="pqi-findings-entry"),
        "pqi1_card_id": "pqi1-card",
        "pqi1_show_back_link": False,
        "pqi2_questions": PQI2_ENVIRONMENT_QUESTIONS,
        "pqi2_form": pqi2_form,
        "pqi2_complete": pqi2_complete,
        "pqi2_score": pqi2_score,
        "pqi2_score_label": pqi2_score_label,
        "pqi2_question_count": pqi2_question_count,
        "pqi2_completed_count": pqi2_completed_count,
        "pqi2_yes_count": pqi2_yes_count,
        "pqi2_percentage": pqi2_percentage,
        "pqi2_optional_note": pqi2_optional_note,
        "pqi2_save_url": url_for("save_pqi2"),
        "pqi4_questions": PQI4_STAFF_FAMILY_OPPORTUNITIES_QUESTIONS,
        "pqi4_form": pqi4_form,
        "pqi4_complete": pqi4_complete,
        "pqi4_score": pqi4_score,
        "pqi4_score_label": pqi4_score_label,
        "pqi4_question_count": pqi4_question_count,
        "pqi4_completed_count": pqi4_completed_count,
        "pqi4_yes_count": pqi4_yes_count,
        "pqi4_percentage": pqi4_percentage,
        "pqi4_optional_note": pqi4_optional_note,
        "pqi4_band_rows": [{"percentage": percentage, "band": band} for percentage, band in PQI4_BAND_MAPPING.items()],
        "pqi4_save_url": url_for("save_pqi4"),
        "pqi5_questions": PQI5_CHILD_PROGRESS_QUESTIONS,
        "pqi5_points": PQI5_QUESTION_POINTS,
        "pqi5_form": pqi5_form,
        "pqi5_complete": pqi5_complete,
        "pqi5_base_points": pqi5_base_points,
        "pqi5_bonus_point": pqi5_bonus_point,
        "pqi5_score": pqi5_score,
        "pqi5_score_label": pqi5_score_label,
        "pqi5_question_count": pqi5_question_count,
        "pqi5_completed_count": pqi5_completed_count,
        "pqi5_save_url": url_for("save_pqi5"),
        "pqi68_cards": pqi68_cards,
        "pqi68_complete_count": pqi68_complete_count,
        "pqi68_complete": pqi68_complete_count == 3,
        "pqi910_cards": pqi910_cards,
        "pqi910_complete_count": pqi910_complete_count,
        "pqi910_complete": pqi910_complete_count == len(pqi910_cards),
        "pqi_progress_numerator": pqi_progress_numerator,
        "pqi_progress_denominator": pqi_progress_denominator,
        "pqi_progress_percentage": pqi_progress_percentage,
        "pqi_progress_units": pqi_progress_units,
        **pqi3_context,
    }


def _normalize_facility_type(value: object) -> str:
    cleaned_value = str(value if value is not None else "").strip()
    if cleaned_value in FACILITY_TYPE_OPTIONS:
        return cleaned_value
    if cleaned_value == "Mixed Age Center":
        return "Mixed Age"
    return FACILITY_TYPE_OPTIONS[0]


def build_pqi_access_context(assessment_row: dict | None = None) -> dict:
    row = assessment_row if assessment_row is not None else get_current_assessment_row()
    facility_type = _normalize_facility_type(row["facility_type"] if row is not None else None)
    allowed_pqis = FACILITY_TYPE_PQI_MAPPING[facility_type]
    return {
        "facility_type": facility_type,
        "pqi_allowed": {str(number): number in allowed_pqis for number in range(1, 11)},
    }


def build_assessment_list_context() -> dict:
    search_query = str(request.args.get("q", "")).strip()
    try:
        page = max(1, int(request.args.get("page", "1")))
    except ValueError:
        page = 1

    normalized_query = normalize_text(search_query)
    result = query_assessment_list(normalized_query, page, ASSESSMENTS_PER_PAGE)

    assessments: list[dict] = []
    for row in result["rows"]:
        status_text = str(row["status"] or "not implemented").strip() or "not implemented"
        assessments.append(
            {
                "id": row["id"],
                "assessment_name": row["assessment_name"],
                "facility_type": row["facility_type"],
                "visit_date_label": format_date_label(row["visit_date"]),
                "owner": str(row["assessor"] or "not implemented").strip() or "not implemented",
                "external_case_number": str(row["external_case_number"] or "").strip(),
                "external_inspection_id": str(row["external_inspection_id"] or "").strip(),
                "status": status_text,
                "status_chip_class": get_status_chip_class(status_text),
                "model": "not implemented",
                "current_result": "not implemented",
            }
        )

    offset = result["offset"]
    total_items = result["total_items"]
    total_pages = result["total_pages"]
    current_page = result["page"]

    visible_start = 0 if total_items == 0 else offset + 1
    visible_end = min(offset + ASSESSMENTS_PER_PAGE, total_items)

    return {
        "assessments": assessments,
        "search_query": search_query,
        "page": current_page,
        "total_pages": total_pages,
        "total_items": total_items,
        "visible_start": visible_start,
        "visible_end": visible_end,
        "has_prev": current_page > 1,
        "has_next": current_page < total_pages,
        "prev_page": current_page - 1,
        "next_page": current_page + 1,
        "page_numbers": list(range(1, total_pages + 1)),
    }


def build_dashboard_context() -> dict:
    draft_assessment_count, modified_today_count, recent_rows = get_dashboard_counts_and_recent()

    recent_assessments: list[dict] = []
    for row in recent_rows:
        status_text = str(row["status"] or "not implemented").strip() or "not implemented"
        recent_assessments.append(
            {
                "id": row["id"],
                "assessment_name": row["assessment_name"],
                "facility_type": row["facility_type"],
                "reference_label": str(row["external_case_number"] or row["external_inspection_id"] or "not implemented").strip() or "not implemented",
                "status": status_text,
                "status_chip_class": get_status_chip_class(status_text),
                "modified_at_label": format_timestamp_label(row["modified_at"]),
                "current_result": "not implemented",
                "action_label": "Continue" if status_text == "draft" else "Open",
            }
        )

    return {
        "draft_assessment_count": draft_assessment_count,
        "modified_today_count": modified_today_count,
        **build_calculation_configuration_context(),
        "recent_assessments": recent_assessments,
    }


def build_calculation_configuration_context() -> dict:
    return {
        "regulation_set_name": REGULATION_SET_NAME,
        "regulation_set_version": REGULATION_SET_VERSION,
        "regulation_effective_date": format_date_label(REGULATION_EFFECTIVE_DATE),
        "calculation_model": CALCULATION_MODEL,
        "calculation_model_version": CALCULATION_MODEL_VERSION,
        "calculation_model_publication_date": format_date_label(CALCULATION_MODEL_PUBLICATION_DATE),
        "structural_reference_table": STRUCTURAL_REFERENCE_TABLE,
        "threshold_set": THRESHOLD_SET,
    }


def build_new_assessment_context() -> dict:
    current_assessment_id = get_current_assessment()
    current_assessment = None

    if current_assessment_id is not None:
        current_assessment = get_assessment_row_by_id(int(current_assessment_id))

    assessment_form = dict(DEFAULT_ASSESSMENT_FORM_VALUES)
    if current_assessment is not None:
        assessment_form.update(
            {
                "program": str(current_assessment["program"] or assessment_form["program"]).strip() or assessment_form["program"],
                "facility_type": _normalize_facility_type(current_assessment["facility_type"] or assessment_form["facility_type"]),
                "inspection_type": str(current_assessment["inspection_type"] or assessment_form["inspection_type"]).strip() or assessment_form["inspection_type"],
                "assessment_date": str(current_assessment["assessment_date"] or assessment_form["assessment_date"]).strip() or assessment_form["assessment_date"],
                "visit_date": str(current_assessment["visit_date"] or assessment_form["visit_date"]).strip() or assessment_form["visit_date"],
                "external_case_number": str(current_assessment["external_case_number"] or assessment_form["external_case_number"]).strip() or assessment_form["external_case_number"],
                "external_inspection_id": str(current_assessment["external_inspection_id"] or assessment_form["external_inspection_id"]).strip() or assessment_form["external_inspection_id"],
                "local_record_name": str(current_assessment["assessment_name"] or assessment_form["local_record_name"]).strip() or assessment_form["local_record_name"],
            }
        )

    assessment_label = get_assessment_label(current_assessment)
    if current_assessment is None:
        assessment_label = "Create assessment"

    return {
        "assessment_form": assessment_form,
        "assessment_label": assessment_label,
        "editing_assessment_id": current_assessment["id"] if current_assessment is not None else None,
        "facility_type_options": FACILITY_TYPE_OPTIONS,
        **build_calculation_configuration_context(),
    }


def build_facility_identification_context() -> dict:
    current_assessment_id = get_current_assessment()
    current_assessment = None

    if current_assessment_id is not None:
        current_assessment = get_assessment_row_by_id(int(current_assessment_id))

    facility_form = dict(DEFAULT_FACILITY_IDENTIFICATION_FORM_VALUES)
    if current_assessment is not None:
        facility_form.update(
            {
                "facility_name": str(current_assessment["facility_name"] or current_assessment["assessment_name"] or facility_form["facility_name"]).strip() or facility_form["facility_name"],
                "facility_identifier": str(current_assessment["facility_identifier"] or facility_form["facility_identifier"]).strip() or facility_form["facility_identifier"],
                "external_system": str(current_assessment["external_system"] or facility_form["external_system"]).strip() or facility_form["external_system"],
                "license_number": str(current_assessment["facility_license_number"] or facility_form["license_number"]).strip() or facility_form["license_number"],
                "provider_account_id": str(current_assessment["provider_id"] or facility_form["provider_account_id"]).strip() or facility_form["provider_account_id"],
                "program_type": str(current_assessment["program_type"] or current_assessment["program"] or facility_form["program_type"]).strip() or facility_form["program_type"],
                "facility_type": _normalize_facility_type(current_assessment["facility_type"] or facility_form["facility_type"]),
                "physical_address": str(current_assessment["physical_address"] or facility_form["physical_address"]).strip() or facility_form["physical_address"],
                "city_state_postal": str(current_assessment["city_state_postal_code"] or facility_form["city_state_postal"]).strip() or facility_form["city_state_postal"],
                "region_office": str(current_assessment["region"] or facility_form["region_office"]).strip() or facility_form["region_office"],
                "provider_operator_name": str(current_assessment["provider_name"] or facility_form["provider_operator_name"]).strip() or facility_form["provider_operator_name"],
                "external_case_number": str(current_assessment["external_case_number"] or facility_form["external_case_number"]).strip() or facility_form["external_case_number"],
                "external_inspection_number": str(current_assessment["external_inspection_id"] or facility_form["external_inspection_number"]).strip() or facility_form["external_inspection_number"],
                "visit_date": str(current_assessment["visit_date"] or facility_form["visit_date"]).strip() or facility_form["visit_date"],
                "assigned_primary_inspector": (
                    str(current_assessment["assessor"]).strip()
                    if current_assessment["assessor"] and str(current_assessment["assessor"]).strip().lower() != "not implemented"
                    else DEFAULT_INSPECTOR_NAME
                ),
            }
        )

    assessment_label = get_assessment_label(current_assessment)

    return {
        "facility_form": facility_form,
        "assessment_label": assessment_label,
        "editing_assessment_id": current_assessment["id"] if current_assessment is not None else None,
        "facility_type_options": FACILITY_TYPE_OPTIONS,
    }


def _sum_pqi_scores(pqi_findings: dict, pqi_keys: tuple[str, ...]) -> int:
    total = 0
    for pqi_key in pqi_keys:
        entry = pqi_findings.get(pqi_key, {})
        if not isinstance(entry, dict):
            continue
        try:
            total += int(entry.get("score"))
        except (TypeError, ValueError):
            continue
    return total


def build_calculation_result() -> dict:
    assessment_row = get_current_assessment_row()
    if assessment_row is None:
        raise ValueError("No assessment selected, unable to calculate")

    progress_context = build_pqi1_context()
    pqi_findings = _load_json_object(assessment_row["pqi_findings"], {})
    allowed_pqis = build_pqi_access_context(assessment_row)["pqi_allowed"]
    pqi_number = sum(
        int(pqi_findings.get(f"pqi{number}", {}).get("score", 0) or 0)
        for number in range(1, 11)
        if allowed_pqis[str(number)] and isinstance(pqi_findings.get(f"pqi{number}"), dict)
    )
    contact_hours = _load_json_object(assessment_row["contact_hours"], {})
    facility_type = _normalize_facility_type(assessment_row["facility_type"])
    outcome = next(
        (label for label, lower_bound in PROGRAM_QUALITY_OUTCOMES.get(facility_type, {}).items() if pqi_number >= lower_bound),
        "Low",
    )
    return {
        "REGULATION_SET_NAME": REGULATION_SET_NAME,
        "REGULATION_SET_VERSION": REGULATION_SET_VERSION,
        "REGULATION_EFFECTIVE_DATE": REGULATION_EFFECTIVE_DATE,
        "CALCULATION_MODEL": CALCULATION_MODEL,
        "CALCULATION_MODEL_VERSION": CALCULATION_MODEL_VERSION,
        "CALCULATION_MODEL_PUBLICATION_DATE": CALCULATION_MODEL_PUBLICATION_DATE,
        "STRUCTURAL_REFERENCE_TABLE": STRUCTURAL_REFERENCE_TABLE,
        "THRESHOLD_SET": THRESHOLD_SET,
        "CALCULATED_CH": contact_hours.get("calculated_ch", ""),
        "RWCH_REFERENCE": contact_hours.get("rwch_reference", ""),
        "PROGRAM_QUALITY_OUTCOME_NUMBER": pqi_number,
        "PROGRAM_QUALITY_OUTCOME": outcome,
        "DATA_COMPLETENESS_NUMBERATOR": progress_context["pqi_progress_numerator"],
        "DATA_COMPLETENESS_DENOMIATOR": progress_context["pqi_progress_denominator"],
        "DATA_COMPLETENESS_PERCENTAGE": progress_context["pqi_progress_percentage"],
        "DATE_CALCULATED": datetime.now().isoformat(timespec="minutes"),
    }


def build_result_summary_context() -> dict:
    assessment_row = get_current_assessment_row()
    result = _load_json_object(assessment_row["calculated_result"], {}) if assessment_row is not None else {}
    contact_hours = _load_json_object(assessment_row["contact_hours"], {}) if assessment_row is not None else {}
    facility_type = _normalize_facility_type(assessment_row["facility_type"]) if assessment_row is not None else ""
    thresholds = PROGRAM_QUALITY_OUTCOMES.get(facility_type, {})
    outcome_number = result.get("PROGRAM_QUALITY_OUTCOME_NUMBER", "--")
    outcome = result.get("PROGRAM_QUALITY_OUTCOME", "No result calculated")
    lower_bound = thresholds.get(outcome)
    higher_bound = next(
        (value - 1 for value in thresholds.values() if lower_bound is not None and value > lower_bound),
        "--",
    )
    outcome_bands = []
    ordered_thresholds = sorted(thresholds.items(), key=lambda item: item[1])
    for index, (label, band_lower_bound) in enumerate(ordered_thresholds):
        next_lower_bound = ordered_thresholds[index + 1][1] if index + 1 < len(ordered_thresholds) else None
        outcome_bands.append(
            {
                "label": label,
                "range": f"{band_lower_bound}-{next_lower_bound - 1}" if next_lower_bound else f"{band_lower_bound}+",
                "active": bool(result) and outcome == label,
            }
        )
    calculated_ch = result.get("CALCULATED_CH", "--")
    rwch_reference = result.get("RWCH_REFERENCE", contact_hours.get("rwch_reference", "--"))
    try:
        structural_is_acceptable = float(calculated_ch) < float(rwch_reference)
    except (TypeError, ValueError):
        structural_is_acceptable = False
    try:
        calculated_ch_position = min(100, max(0, 55 * float(calculated_ch) / float(rwch_reference)))
    except (TypeError, ValueError, ZeroDivisionError):
        calculated_ch_position = None

    return {
        "assessment_label": get_assessment_label(assessment_row),
        "result": result,
        "has_result": bool(result),
        "facility_type": facility_type,
        "outcome_number": outcome_number,
        "outcome": outcome,
        "outcome_range": f"{lower_bound}-{higher_bound}" if lower_bound is not None else "--",
        "outcome_bands": outcome_bands,
        "calculated_ch": calculated_ch,
        "rwch_reference": rwch_reference,
        "calculated_ch_position": calculated_ch_position,
        "rwch_reference_position": 55,
        "completeness_percentage": result.get("DATA_COMPLETENESS_PERCENTAGE", "--"),
        "structural_status_chip_class": "success" if structural_is_acceptable else "danger",
        "structural_status_label": "Acceptable" if structural_is_acceptable else "Needs review",
        "structural_status_message_class": "" if structural_is_acceptable else "danger",
        "structural_status_message": "Calculated CH is below the configured RWCH reference." if structural_is_acceptable else "Calculated CH exceeds the configured RWCH reference.",
        "structural_status_detail": "This indicates an acceptable structural-quality result under the current model." if structural_is_acceptable else "This indicates a structural-quality concern under the current model.",
    }


def build_assessment_progress_context() -> dict:
    assessment_row = get_current_assessment_row()

    if assessment_row is None:
        assessment_row = {
            "id": None,
            "assessment_name": "not implemented",
            "facility_type": "not implemented",
            "assessment_date": None,
            "visit_date": None,
            "program": "not implemented",
            "inspection_type": "not implemented",
            "assessor": "not implemented",
            "status": "not implemented",
            "external_case_number": None,
            "external_inspection_id": None,
            "pqi_findings": "{}",
        }

    status_text = str(assessment_row["status"] or "not implemented").strip() or "not implemented"
    progress_percent = WORKFLOW_PROGRESS_BY_STATUS.get(normalize_text(status_text), 68)
    complete_count = max(0, min(62, round(62 * progress_percent / 100)))
    assessment_id = assessment_row["id"]
    assessment_code = f"ASMT-{assessment_id:05d}" if assessment_id is not None else "No assessment selected"
    assessment_label = get_assessment_label(assessment_row)

    reference_label = str(
        assessment_row["external_case_number"] or assessment_row["external_inspection_id"] or "not implemented"
    ).strip() or "not implemented"
    assessment_name = str(assessment_row["assessment_name"] or "not implemented").strip() or "not implemented"
    facility_type = _normalize_facility_type(assessment_row["facility_type"])
    program = str(assessment_row["program"] or "not implemented").strip() or "not implemented"
    inspection_type = str(assessment_row["inspection_type"] or "not implemented").strip() or "not implemented"
    visit_date_label = format_date_label(assessment_row["visit_date"])

    snapshot_items = [
        {"label": "Regulation set", "value": f"{REGULATION_SET_NAME} {REGULATION_SET_VERSION}"},
        {"label": "Calculation model", "value": f"{CALCULATION_MODEL} v{CALCULATION_MODEL_VERSION}"},
        {"label": "Program", "value": program},
        {"label": "Visit date", "value": visit_date_label},
    ]

    progress_steps = [
        {
            "label": "1. Setup",
            "detail": "Complete",
            "state": "done",
            "href": url_for("screen", screen_id="new-assessment"),
        },
        {
            "label": "2. Identification",
            "detail": "Complete",
            "state": "done",
            "href": url_for("screen", screen_id="facility-identification"),
        },
        {
            "label": "3. Structural quality",
            "detail": "2 warnings",
            "state": "active",
            "href": url_for("screen", screen_id="ch-structural-entry"),
        },
        {
            "label": "4. PQI findings",
            "detail": "28 of 44 complete",
            "state": "pending",
            "href": url_for("screen", screen_id="pqi-findings-entry"),
        },
        {
            "label": "5. Validation",
            "detail": "Not started",
            "state": "pending",
            "href": url_for("screen", screen_id="validation-summary"),
        },
        {
            "label": "6. Calculation",
            "detail": "Not started",
            "state": "pending",
            "href": url_for("screen", screen_id="calculation-review"),
        },
        {
            "label": "7. Result & finalization",
            "detail": "Not started",
            "state": "pending",
            "href": url_for("screen", screen_id="result-summary"),
        },
    ]

    issue_rows = [
        {
            "severity": "danger",
            "label": "Blocking",
            "title": f"{assessment_name} still needs structural review",
            "detail": f"{program} · {facility_type}",
            "button_text": "Go to field",
            "href": url_for("screen", screen_id="ch-structural-entry"),
        },
        {
            "severity": "danger",
            "label": "Blocking",
            "title": "PQI 3 has only 8 of 10 sample records",
            "detail": f"{reference_label} · {inspection_type}",
            "button_text": "Go to sample",
            "href": url_for("screen", screen_id="pqi3-sample"),
        },
        {
            "severity": "warning",
            "label": "Warning",
            "title": "Validation summary has not been reviewed",
            "detail": "Resolve outstanding items before calculation",
            "button_text": "Review",
            "href": url_for("screen", screen_id="validation-summary"),
        },
    ]

    validation_context = build_validation_context()
    blocking_component_keys = set()
    for issue in validation_context["blocking_errors"]:
        if issue.get("kind") == "pqi":
            pqi_number = int(issue["title"].split()[1])
            blocking_component_keys.add("PQI1_5" if pqi_number <= 5 else "PQI6_8" if pqi_number <= 8 else "PQI9_10")
        else:
            blocking_component_keys.add("CONTACT_HOURS")

    pqi_findings = _load_json_object(assessment_row["pqi_findings"], {})
    pqi_points = {
        "PQI1_5": _sum_pqi_scores(pqi_findings, ("pqi1", "pqi2", "pqi3", "pqi4", "pqi5")),
        "PQI6_8": _sum_pqi_scores(pqi_findings, ("pqi6", "pqi7", "pqi8")),
        "PQI9_10": _sum_pqi_scores(pqi_findings, ("pqi9", "pqi10")),
    }

    calculation_component_rows = [
        {
            "name": "Contact Hour Structural Quality",
            "included": INCLUDED_COMPONENTS["CONTACT_HOURS"],
            "status": "Blocking" if INCLUDED_COMPONENTS["CONTACT_HOURS"] and "CONTACT_HOURS" in blocking_component_keys else "Included" if INCLUDED_COMPONENTS["CONTACT_HOURS"] else "Excluded",
            "reason": "All required inputs complete",
            "blocking_reason": "Required inputs are incomplete",
            "contribution": "Structural comparison",
        },
        {
            "name": "PQI 1-5",
            "included": INCLUDED_COMPONENTS["PQI1_5"],
            "status": "Blocking" if INCLUDED_COMPONENTS["PQI1_5"] and "PQI1_5" in blocking_component_keys else "Included" if INCLUDED_COMPONENTS["PQI1_5"] else "Excluded",
            "reason": "Applicable and complete",
            "blocking_reason": "One or more applicable indicators are incomplete",
            "contribution": "--" if "PQI1_5" in blocking_component_keys else f"{pqi_points['PQI1_5']} points",
        },
        {
            "name": "PQI 6-8",
            "included": INCLUDED_COMPONENTS["PQI6_8"],
            "status": "Blocking" if INCLUDED_COMPONENTS["PQI6_8"] and "PQI6_8" in blocking_component_keys else "Included" if INCLUDED_COMPONENTS["PQI6_8"] else "Excluded",
            "reason": "All hierarchical indicators applicable",
            "blocking_reason": "One or more hierarchical indicators are incomplete",
            "contribution": "--" if "PQI6_8" in blocking_component_keys else f"{pqi_points['PQI6_8']} points",
        },
        {
            "name": "PQI 9-10",
            "included": INCLUDED_COMPONENTS["PQI9_10"],
            "status": "Blocking" if INCLUDED_COMPONENTS["PQI9_10"] and "PQI9_10" in blocking_component_keys else "Included" if INCLUDED_COMPONENTS["PQI9_10"] else "Excluded",
            "reason": "All timed observations complete",
            "blocking_reason": "One or more timed observations are incomplete",
            "contribution": "--" if "PQI9_10" in blocking_component_keys else f"{pqi_points['PQI9_10']} points",
        },
        {
            "name": "Attachments and narrative notes",
            "included": INCLUDED_COMPONENTS["ATTACHMENTS_AND_NARRATIVE_NOTES"],
            "status": "Included" if INCLUDED_COMPONENTS["ATTACHMENTS_AND_NARRATIVE_NOTES"] else "Excluded",
            "reason": "Evidence only; not calculation inputs",
            "blocking_reason": "Evidence requirements are incomplete",
            "contribution": "No score contribution",
        },
    ]
    for component in calculation_component_rows:
        if component["status"] == "Blocking":
            component["reason"] = component["blocking_reason"]

    return {
        "assessment_code": assessment_code,
        "assessment_label": assessment_label,
        "assessment_selected": assessment_id is not None,
        **build_calculation_configuration_context(),
        "assessment_name": assessment_name,
        "assessment_status": status_text,
        "assessment_status_chip_class": get_status_chip_class(status_text),
        "assessment_status_label": status_text.title(),
        "reference_label": reference_label,
        "facility_type": facility_type,
        "inspection_type": inspection_type,
        "visit_date_label": visit_date_label,
        "progress_percent": progress_percent,
        "complete_count": complete_count,
        "required_count": 62,
        "current_step_title": "CH Structural Entry",
        "current_step_summary": "Open the evidence entry form and resolve the open findings.",
        "next_step_href": url_for("screen", screen_id="ch-structural-entry"),
        "history_href": url_for("screen", screen_id="audit-history"),
        "validation_href": url_for("screen", screen_id="validation-summary"),
        "progress_steps": progress_steps,
        "issue_rows": issue_rows,
        "calculation_component_rows": calculation_component_rows,
        "blocking_errors": validation_context["blocking_errors"],
        "acknowledged_warning_count": sum(1 for warning in validation_context["warnings"] if warning.get("acknowledged")),
        "unacknowledged_warning_count": sum(1 for warning in validation_context["warnings"] if not warning.get("acknowledged")),
        "calculation_ready": assessment_id is not None and not validation_context["blocking_errors"],
        "snapshot_items": snapshot_items,
        "recommendation_title": "Complete Structural Quality inputs",
        "recommendation_body": "Enter the ratio source and verify the Contact Hour formula before moving to PQI findings.",
        "assessment_banner": f"{reference_label} · {inspection_type} · {visit_date_label}",
    }


def build_validation_context() -> dict:
    assessment_row = get_current_assessment_row()
    assessment_label = get_assessment_label(assessment_row)
    blocking_errors: list[dict] = []

    if assessment_row is not None:
        facility_defaults = DEFAULT_FACILITY_IDENTIFICATION_FORM_VALUES
        field_values = {
            "assessment_name": assessment_row["assessment_name"],
            "program": assessment_row["program"],
            "inspection_type": assessment_row["inspection_type"],
            "assessment_date": assessment_row["assessment_date"],
            "facility_name": assessment_row["facility_name"] or facility_defaults["facility_name"],
            "facility_identifier": assessment_row["facility_identifier"] or facility_defaults["facility_identifier"],
            "license_number": assessment_row["facility_license_number"] or facility_defaults["license_number"],
            "provider_account_id": assessment_row["provider_id"] or facility_defaults["provider_account_id"],
            "program_type": assessment_row["program_type"] or facility_defaults["program_type"],
            "facility_type": assessment_row["facility_type"] or facility_defaults["facility_type"],
            "physical_address": assessment_row["physical_address"] or facility_defaults["physical_address"],
            "city_state_postal": assessment_row["city_state_postal_code"] or facility_defaults["city_state_postal"],
            "region_office": assessment_row["region"] or facility_defaults["region_office"],
            "provider_operator_name": assessment_row["provider_name"] or facility_defaults["provider_operator_name"],
            "external_system": assessment_row["external_system"] or facility_defaults["external_system"],
            "external_case_number": assessment_row["external_case_number"] or facility_defaults["external_case_number"],
            "external_inspection_number": assessment_row["external_inspection_id"] or facility_defaults["external_inspection_number"],
            "visit_date": assessment_row["visit_date"] or facility_defaults["visit_date"],
            "assigned_primary_inspector": assessment_row["assessor"] or facility_defaults["assigned_primary_inspector"],
            "inspector_identifier": "",
            "assessment_notes": "",
        }
        contact_hours = _load_json_object(assessment_row["contact_hours"], {})
        field_values.update(contact_hours)

        field_specs = {
            "assessment_name": ("Assessment name", "Setup", "new-assessment"),
            "program": ("Program", "Setup", "new-assessment"),
            "inspection_type": ("Inspection type", "Setup", "new-assessment"),
            "assessment_date": ("Assessment date", "Setup", "new-assessment"),
            "facility_name": ("Facility name", "Facility Identification", "facility-identification"),
            "facility_identifier": ("Facility identifier", "Facility Identification", "facility-identification"),
            "program_type": ("Program type", "Facility Identification", "facility-identification"),
            "facility_type": ("Facility type", "Facility Identification", "facility-identification"),
            "physical_address": ("Physical address", "Facility Identification", "facility-identification"),
            "city_state_postal": ("City, state, postal code", "Facility Identification", "facility-identification"),
            "external_system": ("External system", "External Record References", "facility-identification"),
            "external_case_number": ("External case number", "External Record References", "facility-identification"),
            "visit_date": ("Visit date", "External Record References", "facility-identification"),
            "assigned_primary_inspector": ("Inspector name", "External Record References", "facility-identification"),
            "to1": ("Facility opens / first staff arrives", "Structural Quality", "ch-structural-entry"),
            "to2": ("Facility closes / last staff leaves", "Structural Quality", "ch-structural-entry"),
            "ta": ("Total teaching / caregiving staff", "Structural Quality", "ch-structural-entry"),
            "nc": ("Children on maximum enrollment day", "Structural Quality", "ch-structural-entry"),
            "th1": ("Last child arrives", "Structural Quality", "ch-structural-entry"),
            "th2": ("First child leaves", "Structural Quality", "ch-structural-entry"),
            "density_model": ("Density model", "Structural Quality", "ch-structural-entry"),
            "required_ratio": ("Legally required adult-child ratio", "Structural Quality", "ch-structural-entry"),
            "ratio_source": ("Adult-child ratio source", "Structural Quality", "ch-structural-entry"),
            "rwch_reference": ("Adult-child ratio reference", "Structural Quality", "ch-structural-entry"),
        }
        total_field_checks = 0
        for requiredness_key, requiredness in (
            ("new-assessment", NON_PQI_FIELD_REQUIREDNESS["new-assessment"]),
            ("facility-identification", NON_PQI_FIELD_REQUIREDNESS["facility-identification"]),
            ("ch-structural-entry", NON_PQI_FIELD_REQUIREDNESS["ch-structural-entry"]),
        ):
            for field_name, is_required in requiredness.items():
                if not is_required:
                    continue
                total_field_checks += 1
                if str(field_values.get(field_name, "") or "").strip():
                    continue
                title, section, target_screen = field_specs[field_name]
                blocking_errors.append({
                    "kind": "field",
                    "title": f"{title} is missing",
                    "detail": "This required field must be completed before calculation.",
                    "location": f"{section} › {('Reference and model selection' if target_screen == 'ch-structural-entry' else section)}",
                    "button_text": "Go to field",
                    "href": url_for("screen", screen_id=target_screen),
                })

        pqi_findings = _load_json_object(assessment_row["pqi_findings"], {})
        pqi_allowed = build_pqi_access_context(assessment_row)["pqi_allowed"]
        pqi_context = build_pqi1_context()
        pqi_completion = {
            "1": pqi_context["pqi1_complete"],
            "2": pqi_context["pqi2_complete"],
            "3": pqi_context["pqi3_complete"],
            "4": pqi_context["pqi4_complete"],
            "5": pqi_context["pqi5_complete"],
            "6": any(card["number"] == 6 and card["status"] == "complete" for card in pqi_context["pqi68_cards"]),
            "7": any(card["number"] == 7 and card["status"] == "complete" for card in pqi_context["pqi68_cards"]),
            "8": any(card["number"] == 8 and card["status"] == "complete" for card in pqi_context["pqi68_cards"]),
            "9": any(card["number"] == 9 and card["status"] == "complete" for card in pqi_context["pqi910_cards"]),
            "10": any(card["number"] == 10 and card["status"] == "complete" for card in pqi_context["pqi910_cards"]),
        }
        pqi_targets = {"3": "pqi3-sample", "6": "pqi6-8-hierarchy", "7": "pqi7", "8": "pqi8", "9": "pqi9-10-timed", "10": "pqi9-10-timed"}
        pqi_names = {"1": "ECE III Educators", "2": "Stimulating Environment", "3": "Curriculum & Assessment", "4": "Staff & Family Opportunities", "5": "Child Progress Reporting", "6": "Language & Interaction", "7": "Learning Environment", "8": "Responsive Care", "9": "Attention", "10": "Warmth"}
        for pqi_number in range(1, 11):
            key = str(pqi_number)
            if pqi_allowed[key] and not pqi_completion[key]:
                blocking_errors.append({
                    "kind": "pqi",
                    "title": f"PQI {pqi_number} is incomplete",
                    "detail": f"Complete {pqi_names[key]} before calculation.",
                    "location": f"PQI Findings › PQI {pqi_number}",
                    "button_text": "Open PQI",
                    "href": url_for("screen", screen_id=pqi_targets.get(key, "pqi-findings-entry")) + (f"#pqi-{key}" if key in {"1", "2", "4", "5"} else ""),
                })

        total_checks = total_field_checks + sum(pqi_allowed.values())
    else:
        total_checks = 0
    warnings: list[dict] = []
    return {
        "assessment_label": assessment_label,
        "assessment_id": assessment_row["id"] if assessment_row is not None else None,
        "blocking_errors": blocking_errors,
        "warnings": warnings,
        "checks_passed": max(0, total_checks - len(blocking_errors) - len(warnings)),
        "all_issues": (blocking_errors + warnings)[:3],
        "all_issue_count": len(blocking_errors) + len(warnings),
        "validation_href": url_for("screen", screen_id="validation-summary"),
        "back_href": url_for("screen", screen_id="assessment-progress"),
    }


def build_duplicate_warning_html() -> Markup:
    current_assessment = get_current_assessment_row()
    if current_assessment is None:
        return Markup("")

    candidate_rows = get_duplicate_candidate_rows(int(current_assessment["id"]))

    reason_texts: list[str] = []
    has_case_match = False
    has_inspection_match = False

    for candidate in candidate_rows:
        candidate_label = f"assessment #{candidate['id']} ({escape(candidate['assessment_name'])})"

        if (
            current_assessment["assessment_date"] == candidate["assessment_date"]
            and current_assessment["visit_date"] == candidate["visit_date"]
            and names_are_similar(current_assessment["assessment_name"], candidate["assessment_name"])
        ):
            reason_texts.append(
                f"an assessment with the same assessment date and visit date as {candidate_label}, and a similar assessment name"
            )

        if current_assessment["external_case_number"] and current_assessment["external_case_number"] == candidate["external_case_number"]:
            has_case_match = True
            reason_texts.append(f"an assessment that has the same external case number as {candidate_label}")

        if current_assessment["external_inspection_id"] and current_assessment["external_inspection_id"] == candidate["external_inspection_id"]:
            has_inspection_match = True
            reason_texts.append(f"an external inspection ID matches {candidate_label}")

    if not reason_texts:
        return Markup("")

    if has_case_match:
        reason_text = next(reason for reason in reason_texts if "external case number" in reason)
    elif has_inspection_match:
        reason_text = next(reason for reason in reason_texts if "external inspection ID" in reason)
    else:
        reason_text = reason_texts[0]

    lead_in = "Multiple possible duplicates found including " if len(reason_texts) > 1 else "Possible duplicate found because "

    warning_html = f"""
        <div class="alert warning">
            <div class="alert-icon">!</div>
            <div>
                <strong>{lead_in}{reason_text}</strong>
            </div>
            <button type="button">Review duplicate</button>
        </div>
    """
    return Markup(warning_html)
