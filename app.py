# region set up

import json
import os
import sqlite3
from difflib import SequenceMatcher
from datetime import datetime
from pathlib import Path

from flask import Flask, abort, jsonify, redirect, render_template, render_template_string, request, session, url_for
from markupsafe import Markup, escape

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY", "dev-only-secret-change-me")

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
CURRENT_ASSESSMENT_SESSION_KEY = "current_assessment_id"
ASSESSMENTS_PER_PAGE = 8

DEFAULT_ASSESSMENT_FORM_VALUES = {
    "program": "Child Care Center",
    "facility_type": "Mixed Age Center",
    "inspection_type": "Annual Monitoring Visit",
    "assessment_date": "2026-07-17",
    "visit_date": "2026-07-14",
    "external_case_number": "CMP-2026-004182",
    "external_inspection_id": "INS-2026-0714-22",
    "local_record_name": "Sunrise Learning Center - Annual 2026",
}

DEFAULT_FACILITY_IDENTIFICATION_FORM_VALUES = {
    "facility_name": "Sunrise Learning Center",
    "facility_identifier": "FAC-008742",
    "license_number": "LIC-CC-21884",
    "provider_account_id": "PRV-004198",
    "program_type": "Child Care Center",
    "facility_type": "Mixed Age Center",
    "physical_address": "1250 Cedar Avenue",
    "city_state_postal": "Olympia, WA 98501",
    "region_office": "Region 3 - South Sound",
    "provider_operator_name": "Sunrise Learning LLC",
    "external_system": "Compass",
    "external_case_number": "CMP-2026-004182",
    "external_inspection_number": "INS-2026-0714-22",
    "visit_date": "2026-07-14",
    "assigned_primary_inspector": "Jordan Davis",
    "inspector_identifier": "EMP-10482",
    "assessment_notes": "Routine annual monitoring visit. Structural and process quality measures collected after the on-site inspection.",
}

STATUS_CLASS_MAP = {
    "draft": "warning",
    "review": "info",
    "provisional": "info",
    "final": "success",
    "archived": "neutral",
    "needs updates": "danger",
    "not implemented": "danger-bright",
}

WORKFLOW_PROGRESS_BY_STATUS = {
    "draft": 68,
    "review": 82,
    "provisional": 90,
    "final": 100,
    "archived": 100,
    "needs updates": 54,
    "not implemented": 68,
}

# endregion set up

# region rendering

def read_fragment(fragment_path: Path) -> str:
    return fragment_path.read_text(encoding="utf-8")


def normalize_text(value: str | None) -> str:
    return " ".join(str(value or "").casefold().split())


def format_date_label(date_value: str | None) -> str:
    value = str(date_value or "").strip()
    if not value:
        return "not implemented"

    for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
        try:
            parsed = datetime.strptime(value, fmt)
            return parsed.strftime("%b %d, %Y")
        except ValueError:
            continue

    return value


def format_timestamp_label(timestamp_value: str | None) -> str:
    value = str(timestamp_value or "").strip()
    if not value:
        return "not implemented"

    parsed_value: datetime | None = None
    for candidate_format in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S.%f",
    ):
        try:
            parsed_value = datetime.strptime(value, candidate_format)
            break
        except ValueError:
            continue

    if parsed_value is None:
        try:
            parsed_value = datetime.fromisoformat(value)
        except ValueError:
            return value

    today = datetime.now().date()
    if parsed_value.date() == today:
        return f"Today, {parsed_value.strftime('%I:%M %p').lstrip('0')}"

    if parsed_value.date().toordinal() == today.toordinal() - 1:
        return f"Yesterday, {parsed_value.strftime('%I:%M %p').lstrip('0')}"

    return parsed_value.strftime("%b %d, %I:%M %p").replace(" 0", " ")


def get_status_chip_class(status_value: str | None) -> str:
    normalized = normalize_text(status_value)
    return STATUS_CLASS_MAP.get(normalized, "neutral")


def build_assessment_list_context() -> dict:
    search_query = str(request.args.get("q", "")).strip()
    try:
        page = max(1, int(request.args.get("page", "1")))
    except ValueError:
        page = 1

    normalized_query = normalize_text(search_query)
    where_clause = ""
    params: list = []

    if normalized_query:
        like_value = f"%{normalized_query}%"
        where_clause = """
            WHERE lower(trim(assessment_name)) LIKE ?
               OR lower(trim(facility_type)) LIKE ?
               OR lower(trim(COALESCE(external_case_number, ''))) LIKE ?
               OR lower(trim(COALESCE(external_inspection_id, ''))) LIKE ?
               OR lower(trim(COALESCE(assessor, ''))) LIKE ?
               OR lower(trim(COALESCE(status, ''))) LIKE ?
        """
        params.extend([like_value, like_value, like_value, like_value, like_value, like_value])

    conn = get_db_connection()
    try:
        total_items = int(
            conn.execute(
                f"""
                SELECT COUNT(*) AS total
                FROM assessments
                {where_clause}
                """,
                params,
            ).fetchone()["total"]
        )

        total_pages = max(1, (total_items + ASSESSMENTS_PER_PAGE - 1) // ASSESSMENTS_PER_PAGE)
        page = min(page, total_pages)
        offset = (page - 1) * ASSESSMENTS_PER_PAGE

        rows = conn.execute(
            f"""
            SELECT
                id,
                assessment_name,
                facility_type,
                visit_date,
                assessor,
                external_case_number,
                external_inspection_id,
                COALESCE(NULLIF(trim(status), ''), 'not implemented') AS status,
                created_at
            FROM assessments
            {where_clause}
            ORDER BY datetime(created_at) DESC, id DESC
            LIMIT ? OFFSET ?
            """,
            [*params, ASSESSMENTS_PER_PAGE, offset],
        ).fetchall()
    finally:
        conn.close()

    assessments: list[dict] = []
    for row in rows:
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

    visible_start = 0 if total_items == 0 else offset + 1
    visible_end = min(offset + ASSESSMENTS_PER_PAGE, total_items)
    page_numbers = list(range(1, total_pages + 1))

    return {
        "assessments": assessments,
        "search_query": search_query,
        "page": page,
        "total_pages": total_pages,
        "total_items": total_items,
        "visible_start": visible_start,
        "visible_end": visible_end,
        "has_prev": page > 1,
        "has_next": page < total_pages,
        "prev_page": page - 1,
        "next_page": page + 1,
        "page_numbers": page_numbers,
    }


def build_dashboard_context() -> dict:
    conn = get_db_connection()
    try:
        draft_assessment_count = int(
            conn.execute(
                """
                SELECT COUNT(*) AS total
                FROM assessments
                WHERE lower(trim(COALESCE(status, ''))) = 'draft'
                """
            ).fetchone()["total"]
        )

        modified_today_count = int(
            conn.execute(
                """
                SELECT COUNT(*) AS total
                FROM assessments
                WHERE date(COALESCE(NULLIF(trim(modified_at), ''), created_at)) = date('now')
                """
            ).fetchone()["total"]
        )

        recent_rows = conn.execute(
            """
            SELECT
                id,
                assessment_name,
                facility_type,
                external_case_number,
                external_inspection_id,
                COALESCE(NULLIF(trim(status), ''), 'not implemented') AS status,
                COALESCE(NULLIF(trim(modified_at), ''), created_at) AS modified_at
            FROM assessments
            ORDER BY datetime(COALESCE(NULLIF(trim(modified_at), ''), created_at)) DESC, id DESC
            LIMIT 3
            """
        ).fetchall()
    finally:
        conn.close()

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


def get_most_recent_assessment_row() -> sqlite3.Row | None:
    conn = get_db_connection()
    try:
        return conn.execute(
            """
            SELECT
                id,
                assessment_name,
                facility_name,
                facility_type,
                assessment_date,
                visit_date,
                program,
                inspection_type,
                assessor,
                status,
                external_case_number,
                external_inspection_id
            FROM assessments
            ORDER BY datetime(COALESCE(NULLIF(trim(modified_at), ''), created_at)) DESC, id DESC
            LIMIT 1
            """
        ).fetchone()
    finally:
        conn.close()


def get_assessment_row_by_id(assessment_id: int) -> sqlite3.Row | None:
    conn = get_db_connection()
    try:
        return conn.execute(
            """
            SELECT
                id,
                assessment_name,
                facility_name,
                facility_type,
                assessment_date,
                visit_date,
                program,
                inspection_type,
                assessor,
                status,
                external_case_number,
                external_inspection_id
            FROM assessments
            WHERE id = ?
            """,
            (assessment_id,),
        ).fetchone()
    finally:
        conn.close()


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


def names_are_similar(left: str | None, right: str | None) -> bool:
    left_text = normalize_text(left)
    right_text = normalize_text(right)

    if not left_text or not right_text:
        return False

    if left_text == right_text:
        return True

    return SequenceMatcher(None, left_text, right_text).ratio() >= 0.82


def get_current_assessment_row() -> sqlite3.Row | None:
    assessment_id = get_current_assessment()
    if assessment_id is None:
        return None

    return get_assessment_row_by_id(int(assessment_id))


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


def upsert_assessment_entry(
    assessment_data: dict,
    *,
    status: str,
    assessment_id: int | None = None,
    existing_assessment: sqlite3.Row | None = None,
) -> int:
    fields = build_assessment_fields(assessment_data, status=status, existing_assessment=existing_assessment)

    conn = get_db_connection()
    try:
        existing_row = None
        if assessment_id is not None:
            existing_row = conn.execute(
                "SELECT id FROM assessments WHERE id = ?",
                (assessment_id,),
            ).fetchone()

        if existing_row is not None:
            conn.execute(
                """
                UPDATE assessments
                SET
                    assessment_name = ?,
                    facility_name = ?,
                    facility_identifier = ?,
                    facility_license_number = ?,
                    physical_address = ?,
                    city_state_postal_code = ?,
                    facility_type = ?,
                    assessment_date = ?,
                    visit_date = ?,
                    program = ?,
                    inspection_type = ?,
                    assessor = ?,
                    status = ?,
                    external_case_number = ?,
                    external_inspection_id = ?,
                    modified_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    fields["assessment_name"],
                    fields["facility_name"],
                    fields["facility_identifier"],
                    fields["facility_license_number"],
                    fields["physical_address"],
                    fields["city_state_postal_code"],
                    fields["facility_type"],
                    fields["assessment_date"],
                    fields["visit_date"],
                    fields["program"],
                    fields["inspection_type"],
                    fields["assessor"],
                    fields["status"],
                    fields["external_case_number"],
                    fields["external_inspection_id"],
                    assessment_id,
                ),
            )
            conn.commit()
            log_storage_event(f"Updated assessment {assessment_id}: {json.dumps(fields, sort_keys=True)}")
            return assessment_id

        cursor = conn.execute(
            """
            INSERT INTO assessments (
                assessment_name,
                facility_name,
                facility_identifier,
                facility_license_number,
                physical_address,
                city_state_postal_code,
                facility_type,
                assessment_date,
                visit_date,
                program,
                inspection_type,
                assessor,
                status,
                external_case_number,
                external_inspection_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                fields["assessment_name"],
                fields["facility_name"],
                fields["facility_identifier"],
                fields["facility_license_number"],
                fields["physical_address"],
                fields["city_state_postal_code"],
                fields["facility_type"],
                fields["assessment_date"],
                fields["visit_date"],
                fields["program"],
                fields["inspection_type"],
                fields["assessor"],
                fields["status"],
                fields["external_case_number"],
                fields["external_inspection_id"],
            ),
        )
        conn.commit()
        assessment_id = int(cursor.lastrowid)
        log_storage_event(f"Created assessment {assessment_id}: {json.dumps(fields, sort_keys=True)}")
        return assessment_id
    finally:
        conn.close()


def build_duplicate_warning_html() -> Markup:
    current_assessment = get_current_assessment_row()
    if current_assessment is None:
        return Markup("")

    conn = get_db_connection()
    try:
        candidate_rows = conn.execute(
            """
            SELECT id, assessment_name, assessment_date, visit_date, external_case_number, external_inspection_id
            FROM assessments
            WHERE id != ?
            ORDER BY created_at DESC, id DESC
            """,
            (current_assessment["id"],),
        ).fetchall()
    finally:
        conn.close()

    trigger_descriptions: list[str] = []

    for candidate in candidate_rows:
        candidate_label = f"assessment #{candidate['id']} ({escape(candidate['assessment_name'])})"

        if (
            current_assessment["assessment_date"] == candidate["assessment_date"]
            and current_assessment["visit_date"] == candidate["visit_date"]
            and names_are_similar(current_assessment["assessment_name"], candidate["assessment_name"])
        ):
            trigger_descriptions.append(
                f"an assessment with the same assessment date and visit date as {candidate_label}, and a similar assessment name"
            )

        if current_assessment["external_case_number"] and current_assessment["external_case_number"] == candidate["external_case_number"]:
            trigger_descriptions.append(f"an assessment that has the same external case number as {candidate_label}")

        if current_assessment["external_inspection_id"] and current_assessment["external_inspection_id"] == candidate["external_inspection_id"]:
            trigger_descriptions.append(f"an external inspection ID matches {candidate_label}")

    if not trigger_descriptions:
        return Markup("")

    if any("external case number matches" in trigger for trigger in trigger_descriptions):
        reason_text = next(trigger for trigger in trigger_descriptions if "external case number matches" in trigger)
    elif any("external inspection ID matches" in trigger for trigger in trigger_descriptions):
        reason_text = next(trigger for trigger in trigger_descriptions if "external inspection ID matches" in trigger)
    else:
        reason_text = next(trigger for trigger in trigger_descriptions if "assessment date and visit date are identical" in trigger)

    if len(trigger_descriptions) > 1:
        lead_in = "Multiple possible duplicates found including "
    else:
        lead_in = "Possible duplicate found because "

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

def render_screen_section(screen_id: str) -> str:
    screen_path = SCREENS_DIR / f"{screen_id}.html"
    content = read_fragment(screen_path)

    if screen_id == "facility-identification":
        content = render_template_string(content, duplicate_warning=build_duplicate_warning_html(), **build_facility_identification_context())
    elif screen_id == "agency-dashboard":
        content = render_template_string(content, **build_dashboard_context())
    elif screen_id == "assessment-list":
        content = render_template_string(content, **build_assessment_list_context())
    elif screen_id == "new-assessment":
        content = render_template_string(content, **build_new_assessment_context())
    elif screen_id == "assessment-progress":
        content = render_template_string(content, **build_assessment_progress_context())

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
            assessment_name TEXT NOT NULL,
            facility_name TEXT NOT NULL DEFAULT '',
            facility_identifier TEXT NOT NULL DEFAULT '',
            facility_license_number TEXT NOT NULL DEFAULT '',
            physical_address TEXT NOT NULL DEFAULT '',
            city_state_postal_code TEXT NOT NULL DEFAULT '',
            facility_type TEXT NOT NULL,
            assessment_date TEXT NOT NULL,
            visit_date TEXT NOT NULL,
            program TEXT NOT NULL,
            inspection_type TEXT NOT NULL,
            assessor TEXT NOT NULL DEFAULT 'not implemented',
            status TEXT NOT NULL DEFAULT 'not implemented',
            external_case_number TEXT,
            external_inspection_id TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            modified_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    assessment_columns = {
        row["name"] for row in conn.execute("PRAGMA table_info(assessments)").fetchall()
    }

    if "data" in assessment_columns:
        legacy_name = f"assessments_legacy_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        conn.execute(f"ALTER TABLE assessments RENAME TO {legacy_name}")
        conn.execute(
            """
            CREATE TABLE assessments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                assessment_name TEXT NOT NULL,
                facility_name TEXT NOT NULL DEFAULT '',
                facility_identifier TEXT NOT NULL DEFAULT '',
                facility_license_number TEXT NOT NULL DEFAULT '',
                physical_address TEXT NOT NULL DEFAULT '',
                city_state_postal_code TEXT NOT NULL DEFAULT '',
                facility_type TEXT NOT NULL,
                assessment_date TEXT NOT NULL,
                visit_date TEXT NOT NULL,
                program TEXT NOT NULL,
                inspection_type TEXT NOT NULL,
                assessor TEXT NOT NULL DEFAULT 'not implemented',
                status TEXT NOT NULL DEFAULT 'not implemented',
                external_case_number TEXT,
                external_inspection_id TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                modified_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        log_storage_event(
            f"Migrated legacy assessments table to {legacy_name} and recreated structured assessments schema"
        )
        assessment_columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(assessments)").fetchall()
        }

    if "status" not in assessment_columns:
        conn.execute("ALTER TABLE assessments ADD COLUMN status TEXT NOT NULL DEFAULT 'not implemented'")
        log_storage_event("Added status column to assessments table with default 'not implemented'")

    if "modified_at" not in assessment_columns:
        conn.execute("ALTER TABLE assessments ADD COLUMN modified_at TEXT")
        log_storage_event("Added modified_at column to assessments table")

    if "facility_name" not in assessment_columns:
        conn.execute("ALTER TABLE assessments ADD COLUMN facility_name TEXT NOT NULL DEFAULT ''")
        log_storage_event("Added facility_name column to assessments table with default ''")

    for column_name, column_definition in {
        "facility_identifier": "TEXT NOT NULL DEFAULT ''",
        "facility_license_number": "TEXT NOT NULL DEFAULT ''",
        "physical_address": "TEXT NOT NULL DEFAULT ''",
        "city_state_postal_code": "TEXT NOT NULL DEFAULT ''",
    }.items():
        if column_name not in assessment_columns:
            conn.execute(f"ALTER TABLE assessments ADD COLUMN {column_name} {column_definition}")
            log_storage_event(f"Added {column_name} column to assessments table with default ''")

    conn.execute(
        """
        UPDATE assessments
        SET status = 'not implemented'
        WHERE status IS NULL OR trim(status) = ''
        """
    )

    conn.execute(
        """
        UPDATE assessments
        SET assessor = 'not implemented'
        WHERE assessor IS NULL OR trim(assessor) = '' OR trim(assessor) = 'unimplemented'
        """
    )

    conn.execute(
        """
        UPDATE assessments
        SET modified_at = COALESCE(NULLIF(trim(modified_at), ''), created_at, CURRENT_TIMESTAMP)
        WHERE modified_at IS NULL OR trim(modified_at) = ''
        """
    )

    conn.execute(
        """
        UPDATE assessments
        SET facility_name = COALESCE(NULLIF(trim(facility_name), ''), NULLIF(trim(assessment_name), ''), '')
        WHERE facility_name IS NULL OR trim(facility_name) = ''
        """
    )

    conn.execute(
        """
        CREATE TRIGGER IF NOT EXISTS assessments_touch_modified_at
        AFTER UPDATE ON assessments
        FOR EACH ROW
        WHEN NEW.modified_at = OLD.modified_at
        BEGIN
            UPDATE assessments
            SET modified_at = CURRENT_TIMESTAMP
            WHERE id = NEW.id;
        END;
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


def set_current_assessment(assessment_id: int) -> None:
    session[CURRENT_ASSESSMENT_SESSION_KEY] = assessment_id


def get_current_assessment() -> int | None:
    return session.get(CURRENT_ASSESSMENT_SESSION_KEY)


def clear_current_assessment() -> None:
    session.pop(CURRENT_ASSESSMENT_SESSION_KEY, None)


def get_payload_value(payload: dict, *keys: str, default: str = "") -> str:
    for key in keys:
        value = str(payload.get(key, "")).strip()
        if value:
            return value
    return default


def build_assessment_fields(assessment_data: dict, *, status: str, existing_assessment: sqlite3.Row | None = None) -> dict:
    existing_values = dict(existing_assessment) if existing_assessment is not None else {}
    fields = {
        "assessment_name": get_payload_value(
            assessment_data,
            "local_record_name",
            "assessment_name",
            default=str(existing_values.get("assessment_name", "")).strip(),
        ),
        "facility_name": get_payload_value(
            assessment_data,
            "facility_name",
            "local_record_name",
            "assessment_name",
            default=str(existing_values.get("facility_name", existing_values.get("assessment_name", ""))).strip(),
        ),
        "facility_identifier": get_payload_value(
            assessment_data,
            "facility_identifier",
            default=str(existing_values.get("facility_identifier", "")).strip(),
        ) or "",
        "facility_license_number": get_payload_value(
            assessment_data,
            "facility_license_number",
            "license_number",
            default=str(existing_values.get("facility_license_number", "")).strip(),
        ) or "",
        "physical_address": get_payload_value(
            assessment_data,
            "physical_address",
            default=str(existing_values.get("physical_address", "")).strip(),
        ) or "",
        "city_state_postal_code": get_payload_value(
            assessment_data,
            "city_state_postal_code",
            "city_state_postal",
            default=str(existing_values.get("city_state_postal_code", "")).strip(),
        ) or "",
        "facility_type": get_payload_value(
            assessment_data,
            "facility_type",
            default=str(existing_values.get("facility_type", "")).strip(),
        ),
        "assessment_date": get_payload_value(
            assessment_data,
            "assessment_date",
            default=str(existing_values.get("assessment_date", "")).strip(),
        ),
        "visit_date": get_payload_value(
            assessment_data,
            "visit_date",
            default=str(existing_values.get("visit_date", "")).strip(),
        ),
        "program": get_payload_value(
            assessment_data,
            "program",
            "program_type",
            default=str(existing_values.get("program", "")).strip(),
        ),
        "inspection_type": get_payload_value(
            assessment_data,
            "inspection_type",
            default=str(existing_values.get("inspection_type", "")).strip(),
        ),
        "assessor": get_payload_value(
            assessment_data,
            "assessor",
            "assigned_primary_inspector",
            default=str(existing_values.get("assessor", "not implemented")).strip() or "not implemented",
        ),
        "status": status,
        "external_case_number": get_payload_value(
            assessment_data,
            "external_case_number",
            default=str(existing_values.get("external_case_number", "")).strip(),
        ) or None,
        "external_inspection_id": get_payload_value(
            assessment_data,
            "external_inspection_id",
            "external_inspection_number",
            default=str(existing_values.get("external_inspection_id", "")).strip(),
        ) or None,
    }

    required_fields = [
        "assessment_name",
        "facility_type",
        "assessment_date",
        "visit_date",
        "program",
        "inspection_type",
    ]
    missing_required = [field for field in required_fields if not fields[field]]
    if missing_required:
        raise ValueError(f"Missing required fields: {', '.join(missing_required)}")

    return fields


def create_assessment_entry(assessment_data: dict) -> int:
    return upsert_assessment_entry(assessment_data, status="not implemented")


def save_assignment_draft(draft_data: dict) -> None:
    current_assessment_id = get_current_assessment()

    current_assessment_row = None
    if current_assessment_id is not None:
        current_assessment_row = get_assessment_row_by_id(int(current_assessment_id))

    assessment_id = upsert_assessment_entry(
        draft_data,
        status="draft",
        assessment_id=current_assessment_id,
        existing_assessment=current_assessment_row,
    )
    set_current_assessment(assessment_id)


def delete_assessments_by_ids(assessment_ids: list[int]) -> int:
    if not assessment_ids:
        return 0

    unique_ids = sorted({int(assessment_id) for assessment_id in assessment_ids})
    placeholders = ", ".join("?" for _ in unique_ids)

    conn = get_db_connection()
    try:
        deleted_count = conn.execute(
            f"DELETE FROM assessments WHERE id IN ({placeholders})",
            unique_ids,
        ).rowcount
        conn.commit()

        if get_current_assessment() in unique_ids:
            session.pop(CURRENT_ASSESSMENT_SESSION_KEY, None)

        log_storage_event(f"Deleted {deleted_count} assessments: {unique_ids}")
        return deleted_count
    finally:
        conn.close()

# endregion storage and logging

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
    data = request.json
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
    return jsonify({"status": "success", "deleted_count": deleted_count})


@app.route("/api/assessments/start", methods=["POST"])
def start_assessment():
    assessment_data = request.get_json(silent=True) or {}

    if not assessment_data:
        return jsonify({"status": "error", "message": "No assessment data provided"}), 400

    current_assessment_id = get_current_assessment()
    current_assessment_row = get_assessment_row_by_id(int(current_assessment_id)) if current_assessment_id is not None else None

    try:
        if current_assessment_row is not None:
            existing_status = str(current_assessment_row["status"] or "not implemented").strip() or "not implemented"
            assessment_id = upsert_assessment_entry(
                assessment_data,
                status=existing_status,
                assessment_id=int(current_assessment_row["id"]),
                existing_assessment=current_assessment_row,
            )
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

if __name__ == "__main__":
    app.run(debug=True)