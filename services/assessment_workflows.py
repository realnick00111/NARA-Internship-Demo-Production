import sqlite3

from constants import DEFAULT_INSPECTOR_NAME
from repositories.assessments import get_assessment_row_by_id, upsert_assessment_fields
from session_state import get_current_assessment, set_current_assessment


def get_payload_value(payload: dict, *keys: str, default: str = "") -> str:
    for key in keys:
        value = str(payload.get(key, "")).strip()
        if value:
            return value
    return default


def build_assessment_fields(
    assessment_data: dict,
    *,
    status: str,
    existing_assessment: sqlite3.Row | None = None,
) -> dict:
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
        )
        or "",
        "external_system": get_payload_value(
            assessment_data,
            "external_system",
            default=str(existing_values.get("external_system", "")).strip(),
        )
        or "",
        "facility_license_number": get_payload_value(
            assessment_data,
            "facility_license_number",
            "license_number",
            default=str(existing_values.get("facility_license_number", "")).strip(),
        )
        or "",
        "physical_address": get_payload_value(
            assessment_data,
            "physical_address",
            default=str(existing_values.get("physical_address", "")).strip(),
        )
        or "",
        "city_state_postal_code": get_payload_value(
            assessment_data,
            "city_state_postal_code",
            "city_state_postal",
            default=str(existing_values.get("city_state_postal_code", "")).strip(),
        )
        or "",
        "facility_type": get_payload_value(
            assessment_data,
            "facility_type",
            default=str(existing_values.get("facility_type", "")).strip(),
        ),
        "provider_name": get_payload_value(
            assessment_data,
            "provider_name",
            "provider_operator_name",
            default=str(existing_values.get("provider_name", "")).strip(),
        )
        or "",
        "provider_id": get_payload_value(
            assessment_data,
            "provider_id",
            "provider_account_id",
            default=str(existing_values.get("provider_id", "")).strip(),
        )
        or "",
        "region": get_payload_value(
            assessment_data,
            "region",
            "region_office",
            default=str(existing_values.get("region", "")).strip(),
        )
        or "",
        "program_type": get_payload_value(
            assessment_data,
            "program_type",
            "program",
            default=str(existing_values.get("program_type", existing_values.get("program", ""))).strip(),
        )
        or get_payload_value(
            assessment_data,
            "program",
            default=str(existing_values.get("program", "")).strip(),
        ),
        "program": get_payload_value(
            assessment_data,
            "program",
            "program_type",
            default=str(existing_values.get("program", existing_values.get("program_type", ""))).strip(),
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
            default=str(existing_values.get("assessor", DEFAULT_INSPECTOR_NAME)).strip() or DEFAULT_INSPECTOR_NAME,
        ),
        "status": status,
        "external_case_number": get_payload_value(
            assessment_data,
            "external_case_number",
            default=str(existing_values.get("external_case_number", "")).strip(),
        )
        or None,
        "external_inspection_id": get_payload_value(
            assessment_data,
            "external_inspection_id",
            "external_inspection_number",
            default=str(existing_values.get("external_inspection_id", "")).strip(),
        )
        or None,
    }

    required_fields = [
        "assessment_name",
        "facility_type",
        "assessment_date",
        "visit_date",
        "program_type",
        "inspection_type",
    ]
    missing_required = [field for field in required_fields if not fields[field]]
    if missing_required:
        raise ValueError(f"Missing required fields: {', '.join(missing_required)}")

    return fields


def create_assessment_entry(assessment_data: dict) -> int:
    fields = build_assessment_fields(assessment_data, status="draft")
    return upsert_assessment_fields(fields)


def save_assignment_draft(draft_data: dict) -> None:
    current_assessment_id = get_current_assessment()

    current_assessment_row = None
    if current_assessment_id is not None:
        current_assessment_row = get_assessment_row_by_id(int(current_assessment_id))

    fields = build_assessment_fields(draft_data, status="draft", existing_assessment=current_assessment_row)
    assessment_id = upsert_assessment_fields(fields, assessment_id=current_assessment_id)
    set_current_assessment(assessment_id)
