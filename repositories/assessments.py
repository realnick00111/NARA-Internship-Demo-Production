import json
import sqlite3

from constants import DEFAULT_INSPECTOR_NAME
from db import get_db_connection, log_storage_event


ASSESSMENT_ROW_SELECT = """
    SELECT
        a.id,
        a.assessment_name,
        a.facility_id,
        a.facility_identifier AS assessment_facility_identifier,
        a.external_system,
        f.identifier AS facility_record_identifier,
        COALESCE(NULLIF(trim(f.identifier), ''), NULLIF(trim(a.facility_identifier), '')) AS facility_identifier,
        a.assessment_date,
        a.visit_date,
        a.inspection_type,
        a.assessor,
        COALESCE(NULLIF(trim(a.status), ''), 'draft') AS status,
        a.external_case_number,
        a.external_inspection_id,
        COALESCE(NULLIF(trim(a.contact_hours), ''), '{}') AS contact_hours,
        COALESCE(NULLIF(trim(a.pqi_findings), ''), '{}') AS pqi_findings,
        COALESCE(NULLIF(trim(a.calculated_result), ''), '{}') AS calculated_result,
        a.created_at,
        a.modified_at,
        COALESCE(NULLIF(trim(f.name), ''), a.assessment_name) AS facility_name,
        COALESCE(NULLIF(trim(f.license_number), ''), '') AS facility_license_number,
        COALESCE(NULLIF(trim(f.physical_address), ''), '') AS physical_address,
        COALESCE(NULLIF(trim(f.city_state_postal_code), ''), '') AS city_state_postal_code,
        COALESCE(NULLIF(trim(f.type), ''), '') AS facility_type,
        COALESCE(NULLIF(trim(f.provider_name), ''), '') AS provider_name,
        COALESCE(NULLIF(trim(f.provider_id), ''), '') AS provider_id,
        COALESCE(NULLIF(trim(f.region), ''), '') AS region,
        COALESCE(NULLIF(trim(f.program_type), ''), '') AS program,
        COALESCE(NULLIF(trim(f.program_type), ''), '') AS program_type
    FROM assessments a
    LEFT JOIN facilities f ON f.id = a.facility_id
"""


def _clean_text(value: object, default: str = "") -> str:
    return str(value if value is not None else default).strip()


def _json_text(value: object, default: object) -> str:
    if value is None:
        return json.dumps(default)

    if isinstance(value, str):
        cleaned_value = value.strip()
        if not cleaned_value:
            return json.dumps(default)
        try:
            parsed_value = json.loads(cleaned_value)
        except json.JSONDecodeError:
            return json.dumps(default)
        return json.dumps(parsed_value)

    return json.dumps(value)


def _json_object(value: object, default: dict) -> dict:
    if isinstance(value, dict):
        return value

    if value is None:
        return dict(default)

    cleaned_value = str(value).strip()
    if not cleaned_value:
        return dict(default)

    try:
        parsed_value = json.loads(cleaned_value)
    except json.JSONDecodeError:
        return dict(default)

    return parsed_value if isinstance(parsed_value, dict) else dict(default)


def _facility_fields_from_payload(fields: dict) -> dict[str, str]:
    return {
        "identifier": _clean_text(fields.get("facility_identifier"), fields.get("assessment_facility_identifier", "")),
        "name": _clean_text(fields.get("facility_name"), fields.get("assessment_name", "")),
        "license_number": _clean_text(fields.get("facility_license_number"), fields.get("license_number", "")),
        "physical_address": _clean_text(fields.get("physical_address")),
        "city_state_postal_code": _clean_text(fields.get("city_state_postal_code"), fields.get("city_state_postal", "")),
        "type": _clean_text(fields.get("facility_type")),
        "provider_name": _clean_text(fields.get("provider_name"), fields.get("provider_operator_name", "")),
        "provider_id": _clean_text(fields.get("provider_id"), fields.get("provider_account_id", "")),
        "region": _clean_text(fields.get("region"), fields.get("region_office", "")),
        "program_type": _clean_text(fields.get("program_type"), fields.get("program", "")),
    }


def _assessment_fields_from_payload(fields: dict) -> dict[str, str | None]:
    return {
        "assessment_name": _clean_text(fields.get("assessment_name"), fields.get("local_record_name", "")),
        "facility_identifier": _clean_text(fields.get("facility_identifier"), fields.get("assessment_facility_identifier", "")),
        "external_system": _clean_text(fields.get("external_system"), fields.get("external_system", "")),
        "assessment_date": _clean_text(fields.get("assessment_date")),
        "visit_date": _clean_text(fields.get("visit_date")),
        "inspection_type": _clean_text(fields.get("inspection_type")),
        "assessor": _clean_text(fields.get("assessor"), DEFAULT_INSPECTOR_NAME) or DEFAULT_INSPECTOR_NAME,
        "status": _clean_text(fields.get("status"), "draft") or "draft",
        "external_case_number": _clean_text(fields.get("external_case_number")) or None,
        "external_inspection_id": _clean_text(fields.get("external_inspection_id")) or None,
    }


def _json_fields_from_payload(fields: dict, existing_row: sqlite3.Row | None = None) -> dict[str, str]:
    existing_values = dict(existing_row) if existing_row is not None else {}
    contact_hours_value = fields.get("contact_hours", existing_values.get("contact_hours", {}))
    pqi_findings_value = fields.get("pqi_findings", existing_values.get("pqi_findings", {}))
    return {
        "contact_hours": _json_text(contact_hours_value, {}),
        "pqi_findings": _json_text(pqi_findings_value, {}),
    }


def _upsert_facility(conn: sqlite3.Connection, fields: dict, facility_id: int | None = None) -> int:
    facility_fields = _facility_fields_from_payload(fields)

    if facility_id is not None:
        existing_facility = conn.execute("SELECT id FROM facilities WHERE id = ?", (facility_id,)).fetchone()
        if existing_facility is not None:
            conn.execute(
                """
                UPDATE facilities
                SET
                    identifier = ?,
                    name = ?,
                    license_number = ?,
                    physical_address = ?,
                    city_state_postal_code = ?,
                    type = ?,
                    provider_name = ?,
                    provider_id = ?,
                    region = ?,
                    program_type = ?
                WHERE id = ?
                """,
                (
                    facility_fields["identifier"],
                    facility_fields["name"],
                    facility_fields["license_number"],
                    facility_fields["physical_address"],
                    facility_fields["city_state_postal_code"],
                    facility_fields["type"],
                    facility_fields["provider_name"],
                    facility_fields["provider_id"],
                    facility_fields["region"],
                    facility_fields["program_type"],
                    facility_id,
                ),
            )
            return facility_id

    cursor = conn.execute(
        """
        INSERT INTO facilities (
            identifier,
            name,
            license_number,
            physical_address,
            city_state_postal_code,
            type,
            provider_name,
            provider_id,
            region,
            program_type
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            facility_fields["identifier"],
            facility_fields["name"],
            facility_fields["license_number"],
            facility_fields["physical_address"],
            facility_fields["city_state_postal_code"],
            facility_fields["type"],
            facility_fields["provider_name"],
            facility_fields["provider_id"],
            facility_fields["region"],
            facility_fields["program_type"],
        ),
    )
    return int(cursor.lastrowid)


def _fetch_assessment_row(conn: sqlite3.Connection, assessment_id: int) -> sqlite3.Row | None:
    return conn.execute(
        f"""
        {ASSESSMENT_ROW_SELECT}
        WHERE a.id = ?
        """,
        (assessment_id,),
    ).fetchone()


def _fetch_recent_assessment_row(conn: sqlite3.Connection) -> sqlite3.Row | None:
    return conn.execute(
        f"""
        {ASSESSMENT_ROW_SELECT}
        ORDER BY datetime(COALESCE(NULLIF(trim(a.modified_at), ''), a.created_at)) DESC, a.id DESC
        LIMIT 1
        """
    ).fetchone()


def get_most_recent_assessment_row() -> sqlite3.Row | None:
    conn = get_db_connection()
    try:
        return _fetch_recent_assessment_row(conn)
    finally:
        conn.close()


def get_assessment_row_by_id(assessment_id: int) -> sqlite3.Row | None:
    conn = get_db_connection()
    try:
        return _fetch_assessment_row(conn, assessment_id)
    finally:
        conn.close()


def build_assessment_input_snapshot(assessment_id: int) -> dict | None:
    row = get_assessment_row_by_id(assessment_id)
    if row is None:
        return None

    return {
        "format": "cceehm-assessment-input",
        "version": 1,
        "assessment": {
            "assessment_name": _clean_text(row["assessment_name"]),
            "facility_identifier": _clean_text(row["assessment_facility_identifier"]),
            "external_system": _clean_text(row["external_system"]),
            "assessment_date": _clean_text(row["assessment_date"]),
            "visit_date": _clean_text(row["visit_date"]),
            "inspection_type": _clean_text(row["inspection_type"]),
            "assessor": _clean_text(row["assessor"], "not implemented") or "not implemented",
            "status": _clean_text(row["status"], "draft") or "draft",
            "external_case_number": row["external_case_number"],
            "external_inspection_id": row["external_inspection_id"],
            "contact_hours": _json_object(row["contact_hours"], {}),
            "pqi_findings": _json_object(row["pqi_findings"], {}),
        },
        "facility": {
            "identifier": _clean_text(row["facility_record_identifier"], row["assessment_facility_identifier"]),
            "name": _clean_text(row["facility_name"]),
            "license_number": _clean_text(row["facility_license_number"]),
            "physical_address": _clean_text(row["physical_address"]),
            "city_state_postal_code": _clean_text(row["city_state_postal_code"]),
            "type": _clean_text(row["facility_type"]),
            "provider_name": _clean_text(row["provider_name"]),
            "provider_id": _clean_text(row["provider_id"]),
            "region": _clean_text(row["region"]),
            "program_type": _clean_text(row["program_type"]),
        },
    }


def import_assessment_input_snapshot(snapshot: dict) -> int:
    assessment_payload = snapshot.get("assessment")
    facility_payload = snapshot.get("facility")
    if not isinstance(assessment_payload, dict) or not isinstance(facility_payload, dict):
        raise ValueError("Snapshot must contain assessment and facility objects")

    fields = dict(facility_payload)
    fields["facility_identifier"] = facility_payload.get("identifier", "")
    fields["facility_name"] = facility_payload.get("name", "")
    fields["facility_license_number"] = facility_payload.get("license_number", "")
    fields["facility_type"] = facility_payload.get("type", "")
    fields["provider_name"] = facility_payload.get("provider_name", "")
    fields["provider_id"] = facility_payload.get("provider_id", "")
    fields["region"] = facility_payload.get("region", "")
    fields["program_type"] = facility_payload.get("program_type", "")
    fields.update(assessment_payload)
    status = _clean_text(assessment_payload.get("status"), "draft") or "draft"
    fields = {
        **fields,
        "contact_hours": assessment_payload.get("contact_hours", {}),
        "pqi_findings": assessment_payload.get("pqi_findings", {}),
    }
    facility_fields = _facility_fields_from_payload(fields)
    assessment_fields = _assessment_fields_from_payload(fields)
    assessment_fields["status"] = status
    missing_required = [
        field_name
        for field_name, value in {
            "assessment_name": assessment_fields["assessment_name"],
            "facility_type": facility_fields["type"],
            "assessment_date": assessment_fields["assessment_date"],
            "visit_date": assessment_fields["visit_date"],
            "program_type": facility_fields["program_type"],
            "inspection_type": assessment_fields["inspection_type"],
        }.items()
        if not value
    ]
    if missing_required:
        raise ValueError(f"Missing required fields: {', '.join(missing_required)}")

    json_fields = _json_fields_from_payload(fields)

    conn = get_db_connection()
    try:
        facility_id = _upsert_facility(conn, fields)
        cursor = conn.execute(
            """
            INSERT INTO assessments (
                assessment_name,
                facility_id,
                facility_identifier,
                external_system,
                assessment_date,
                visit_date,
                inspection_type,
                assessor,
                status,
                external_case_number,
                external_inspection_id,
                contact_hours,
                pqi_findings
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                assessment_fields["assessment_name"],
                facility_id,
                assessment_fields["facility_identifier"],
                assessment_fields["external_system"],
                assessment_fields["assessment_date"],
                assessment_fields["visit_date"],
                assessment_fields["inspection_type"],
                assessment_fields["assessor"],
                assessment_fields["status"],
                assessment_fields["external_case_number"],
                assessment_fields["external_inspection_id"],
                json_fields["contact_hours"],
                json_fields["pqi_findings"],
            ),
        )
        conn.commit()
        new_assessment_id = int(cursor.lastrowid)
        log_storage_event(f"Imported assessment input snapshot as assessment {new_assessment_id}")
        return new_assessment_id
    finally:
        conn.close()
def upsert_assessment_fields(fields: dict, *, assessment_id: int | None = None) -> int:
    conn = get_db_connection()
    try:
        existing_row = _fetch_assessment_row(conn, int(assessment_id)) if assessment_id is not None else None
        facility_id = _upsert_facility(conn, fields, int(existing_row["facility_id"]) if existing_row and existing_row["facility_id"] is not None else None)
        assessment_fields = _assessment_fields_from_payload(fields)
        json_fields = _json_fields_from_payload(fields, existing_row)

        if existing_row is not None:
            conn.execute(
                """
                UPDATE assessments
                SET
                    assessment_name = ?,
                    facility_id = ?,
                    facility_identifier = ?,
                    external_system = ?,
                    assessment_date = ?,
                    visit_date = ?,
                    inspection_type = ?,
                    assessor = ?,
                    status = ?,
                    external_case_number = ?,
                    external_inspection_id = ?,
                    contact_hours = ?,
                    pqi_findings = ?,
                    modified_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    assessment_fields["assessment_name"],
                    facility_id,
                    assessment_fields["facility_identifier"],
                    assessment_fields["external_system"],
                    assessment_fields["assessment_date"],
                    assessment_fields["visit_date"],
                    assessment_fields["inspection_type"],
                    assessment_fields["assessor"],
                    assessment_fields["status"],
                    assessment_fields["external_case_number"],
                    assessment_fields["external_inspection_id"],
                    json_fields["contact_hours"],
                    json_fields["pqi_findings"],
                    assessment_id,
                ),
            )
            conn.commit()
            log_storage_event(f"Updated assessment {assessment_id}: {fields}")
            return assessment_id

        cursor = conn.execute(
            """
            INSERT INTO assessments (
                assessment_name,
                facility_id,
                facility_identifier,
                external_system,
                assessment_date,
                visit_date,
                inspection_type,
                assessor,
                status,
                external_case_number,
                external_inspection_id,
                contact_hours,
                pqi_findings
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                assessment_fields["assessment_name"],
                facility_id,
                assessment_fields["facility_identifier"],
                assessment_fields["external_system"],
                assessment_fields["assessment_date"],
                assessment_fields["visit_date"],
                assessment_fields["inspection_type"],
                assessment_fields["assessor"],
                assessment_fields["status"],
                assessment_fields["external_case_number"],
                assessment_fields["external_inspection_id"],
                json_fields["contact_hours"],
                json_fields["pqi_findings"],
            ),
        )
        conn.commit()
        new_assessment_id = int(cursor.lastrowid)
        log_storage_event(f"Created assessment {new_assessment_id}: {fields}")
        return new_assessment_id
    finally:
        conn.close()


def update_assessment_json_fields(
    assessment_id: int,
    *,
    contact_hours: object | None = None,
    pqi_findings: object | None = None,
    calculated_result: object | None = None,
) -> None:
    updates: list[str] = []
    values: list[object] = []

    if contact_hours is not None:
        updates.append("contact_hours = ?")
        values.append(_json_text(contact_hours, {}))

    if pqi_findings is not None:
        updates.append("pqi_findings = ?")

    if calculated_result is not None:
        updates.append("calculated_result = ?")

    if not updates:
        return

    conn = get_db_connection()
    try:
        existing_row = _fetch_assessment_row(conn, int(assessment_id))
        if existing_row is None:
            raise ValueError("No assessment selected, unable to save")

        if pqi_findings is not None:
            existing_pqi_findings = _json_object(existing_row["pqi_findings"], {})
            incoming_pqi_findings = _json_object(pqi_findings, {})
            merged_pqi_findings = dict(existing_pqi_findings)
            merged_pqi_findings.update(incoming_pqi_findings)
            values.append(_json_text(merged_pqi_findings, {}))

        if calculated_result is not None:
            values.append(_json_text(calculated_result, {}))

        conn.execute(
            f"""
            UPDATE assessments
            SET {', '.join(updates)}, modified_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            [*values, assessment_id],
        )
        conn.commit()
        log_storage_event(f"Updated assessment {assessment_id} JSON fields: {', '.join(name.split(' = ')[0] for name in updates)}")
    finally:
        conn.close()


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
        log_storage_event(f"Deleted {deleted_count} assessments: {unique_ids}")
        return deleted_count
    finally:
        conn.close()


def query_assessment_list(normalized_query: str, page: int, per_page: int) -> dict:
    where_clause = ""
    params: list[str] = []

    if normalized_query:
        like_value = f"%{normalized_query}%"
        where_clause = """
            WHERE lower(trim(assessment_name)) LIKE ?
               OR lower(trim(COALESCE(f.name, ''))) LIKE ?
               OR lower(trim(COALESCE(f.type, ''))) LIKE ?
               OR lower(trim(COALESCE(f.identifier, a.facility_identifier, ''))) LIKE ?
               OR lower(trim(COALESCE(external_case_number, ''))) LIKE ?
               OR lower(trim(COALESCE(external_inspection_id, ''))) LIKE ?
               OR lower(trim(COALESCE(assessor, ''))) LIKE ?
               OR lower(trim(COALESCE(status, ''))) LIKE ?
        """
        params.extend([like_value, like_value, like_value, like_value, like_value, like_value, like_value, like_value])

    conn = get_db_connection()
    try:
        total_items = int(
            conn.execute(
                f"""
                SELECT COUNT(*) AS total
                FROM assessments a
                LEFT JOIN facilities f ON f.id = a.facility_id
                {where_clause}
                """,
                params,
            ).fetchone()["total"]
        )

        total_pages = max(1, (total_items + per_page - 1) // per_page)
        page = min(page, total_pages)
        offset = (page - 1) * per_page

        rows = conn.execute(
            f"""
            SELECT
                a.id,
                a.assessment_name,
                COALESCE(NULLIF(trim(f.type), ''), '') AS facility_type,
                a.visit_date,
                a.assessor,
                a.external_case_number,
                a.external_inspection_id,
                COALESCE(NULLIF(trim(a.status), ''), 'not implemented') AS status,
                a.created_at
            FROM assessments a
            LEFT JOIN facilities f ON f.id = a.facility_id
            {where_clause}
            ORDER BY datetime(a.created_at) DESC, a.id DESC
            LIMIT ? OFFSET ?
            """,
            [*params, per_page, offset],
        ).fetchall()
    finally:
        conn.close()

    return {
        "rows": rows,
        "total_items": total_items,
        "total_pages": total_pages,
        "page": page,
        "offset": offset,
    }


def get_dashboard_counts_and_recent() -> tuple[int, int, list[sqlite3.Row]]:
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
                a.id,
                a.assessment_name,
                COALESCE(NULLIF(trim(f.type), ''), '') AS facility_type,
                a.external_case_number,
                a.external_inspection_id,
                COALESCE(NULLIF(trim(a.status), ''), 'not implemented') AS status,
                COALESCE(NULLIF(trim(a.modified_at), ''), a.created_at) AS modified_at
            FROM assessments a
            LEFT JOIN facilities f ON f.id = a.facility_id
            ORDER BY datetime(COALESCE(NULLIF(trim(a.modified_at), ''), a.created_at)) DESC, a.id DESC
            LIMIT 3
            """
        ).fetchall()
    finally:
        conn.close()

    return draft_assessment_count, modified_today_count, recent_rows


def get_duplicate_candidate_rows(current_assessment_id: int) -> list[sqlite3.Row]:
    conn = get_db_connection()
    try:
        return conn.execute(
            """
            SELECT id, assessment_name, assessment_date, visit_date, external_case_number, external_inspection_id
            FROM assessments
            WHERE id != ?
            ORDER BY created_at DESC, id DESC
            """,
            (current_assessment_id,),
        ).fetchall()
    finally:
        conn.close()
