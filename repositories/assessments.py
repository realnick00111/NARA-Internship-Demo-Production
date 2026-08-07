import sqlite3

from db import get_db_connection, log_storage_event


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


def upsert_assessment_fields(fields: dict, *, assessment_id: int | None = None) -> int:
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
            log_storage_event(f"Updated assessment {assessment_id}: {fields}")
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
        new_assessment_id = int(cursor.lastrowid)
        log_storage_event(f"Created assessment {new_assessment_id}: {fields}")
        return new_assessment_id
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

        total_pages = max(1, (total_items + per_page - 1) // per_page)
        page = min(page, total_pages)
        offset = (page - 1) * per_page

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
