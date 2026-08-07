from flask import request, url_for
from markupsafe import Markup, escape

from constants import (
    ASSESSMENTS_PER_PAGE,
    DEFAULT_ASSESSMENT_FORM_VALUES,
    DEFAULT_FACILITY_IDENTIFICATION_FORM_VALUES,
    WORKFLOW_PROGRESS_BY_STATUS,
)
from repositories.assessments import (
    get_assessment_row_by_id,
    get_dashboard_counts_and_recent,
    get_duplicate_candidate_rows,
    get_most_recent_assessment_row,
    query_assessment_list,
)
from services.formatters import (
    format_date_label,
    format_timestamp_label,
    get_status_chip_class,
    names_are_similar,
    normalize_text,
)
from session_state import get_current_assessment


def get_current_assessment_row() -> dict | None:
    assessment_id = get_current_assessment()
    if assessment_id is None:
        return None
    return get_assessment_row_by_id(int(assessment_id))


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
        "recent_assessments": recent_assessments,
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
                "facility_type": str(current_assessment["facility_type"] or assessment_form["facility_type"]).strip() or assessment_form["facility_type"],
                "inspection_type": str(current_assessment["inspection_type"] or assessment_form["inspection_type"]).strip() or assessment_form["inspection_type"],
                "assessment_date": str(current_assessment["assessment_date"] or assessment_form["assessment_date"]).strip() or assessment_form["assessment_date"],
                "visit_date": str(current_assessment["visit_date"] or assessment_form["visit_date"]).strip() or assessment_form["visit_date"],
                "external_case_number": str(current_assessment["external_case_number"] or assessment_form["external_case_number"]).strip() or assessment_form["external_case_number"],
                "external_inspection_id": str(current_assessment["external_inspection_id"] or assessment_form["external_inspection_id"]).strip() or assessment_form["external_inspection_id"],
                "local_record_name": str(current_assessment["assessment_name"] or assessment_form["local_record_name"]).strip() or assessment_form["local_record_name"],
            }
        )

    return {
        "assessment_form": assessment_form,
        "editing_assessment_id": current_assessment["id"] if current_assessment is not None else None,
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
                "facility_identifier": str(current_assessment["external_case_number"] or current_assessment["external_inspection_id"] or facility_form["facility_identifier"]).strip() or facility_form["facility_identifier"],
                "program_type": str(current_assessment["program"] or facility_form["program_type"]).strip() or facility_form["program_type"],
                "facility_type": str(current_assessment["facility_type"] or facility_form["facility_type"]).strip() or facility_form["facility_type"],
                "external_case_number": str(current_assessment["external_case_number"] or facility_form["external_case_number"]).strip() or facility_form["external_case_number"],
                "external_inspection_number": str(current_assessment["external_inspection_id"] or facility_form["external_inspection_number"]).strip() or facility_form["external_inspection_number"],
                "visit_date": str(current_assessment["visit_date"] or facility_form["visit_date"]).strip() or facility_form["visit_date"],
                "assigned_primary_inspector": str(current_assessment["assessor"] or facility_form["assigned_primary_inspector"]).strip() or facility_form["assigned_primary_inspector"],
            }
        )

    return {
        "facility_form": facility_form,
        "editing_assessment_id": current_assessment["id"] if current_assessment is not None else None,
    }


def build_assessment_progress_context() -> dict:
    assessment_row = get_current_assessment_row() or get_most_recent_assessment_row()

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
        }

    status_text = str(assessment_row["status"] or "not implemented").strip() or "not implemented"
    progress_percent = WORKFLOW_PROGRESS_BY_STATUS.get(normalize_text(status_text), 68)
    complete_count = max(0, min(62, round(62 * progress_percent / 100)))
    assessment_id = assessment_row["id"]
    assessment_code = f"ASMT-{assessment_id:05d}" if assessment_id is not None else "ASMT-not implemented"

    reference_label = str(
        assessment_row["external_case_number"] or assessment_row["external_inspection_id"] or "not implemented"
    ).strip() or "not implemented"
    assessment_name = str(assessment_row["assessment_name"] or "not implemented").strip() or "not implemented"
    facility_type = str(assessment_row["facility_type"] or "not implemented").strip() or "not implemented"
    program = str(assessment_row["program"] or "not implemented").strip() or "not implemented"
    inspection_type = str(assessment_row["inspection_type"] or "not implemented").strip() or "not implemented"
    visit_date_label = format_date_label(assessment_row["visit_date"])

    snapshot_items = [
        {"label": "Regulation set", "value": "Evergreen Center Standards 2026.1"},
        {"label": "Scoring model", "value": "CCEEHM v1.2"},
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

    return {
        "assessment_code": assessment_code,
        "assessment_name": assessment_name,
        "assessment_status": status_text,
        "assessment_status_chip_class": get_status_chip_class(status_text),
        "assessment_status_label": status_text.title(),
        "reference_label": reference_label,
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
        "snapshot_items": snapshot_items,
        "recommendation_title": "Complete Structural Quality inputs",
        "recommendation_body": "Enter the ratio source and verify the Contact Hour formula before moving to PQI findings.",
        "assessment_banner": f"{reference_label} · {inspection_type} · {visit_date_label}",
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
