import sqlite3
from datetime import datetime

from constants import DATABASE_TABLES, DATA_STORAGE_DIR, DB_PATH, LOGS_PATH


def log_storage_event(message: str) -> None:
    DATA_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().isoformat(timespec="seconds")
    with LOGS_PATH.open("a", encoding="utf-8") as log_file:
        log_file.write(f"[{timestamp}] {message}\\n")


def clear_logs() -> None:
    if LOGS_PATH.exists():
        LOGS_PATH.unlink()
        log_storage_event("Cleared all logs.")


def _get_table_columns(conn: sqlite3.Connection, table_name: str) -> set[str]:
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()}


def _add_missing_columns(conn: sqlite3.Connection, table_name: str, column_definitions: dict[str, str]) -> None:
    existing_columns = _get_table_columns(conn, table_name)
    for column_name, column_sql in column_definitions.items():
        if column_name not in existing_columns:
            conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_sql}")


def _reset_storage_schema(conn: sqlite3.Connection) -> None:
    conn.execute("DROP TABLE IF EXISTS assessments")
    conn.execute("DROP TABLE IF EXISTS facilities")


def ensure_storage_schema(conn: sqlite3.Connection) -> None:
    expected_facility_columns = {
        "id",
        "identifier",
        "name",
        "license_number",
        "physical_address",
        "city_state_postal_code",
        "type",
        "provider_name",
        "provider_id",
        "region",
        "program_type",
    }
    expected_assessment_columns = {
        "id",
        "assessment_name",
        "facility_id",
        "facility_identifier",
        "external_system",
        "assessment_date",
        "visit_date",
        "inspection_type",
        "assessor",
        "status",
        "external_case_number",
        "external_inspection_id",
        "contact_hours",
        "pqi_findings",
        "created_at",
        "modified_at",
    }

    existing_tables = {
        row["name"]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    }

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS facilities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            identifier TEXT NOT NULL DEFAULT '',
            name TEXT NOT NULL DEFAULT '',
            license_number TEXT NOT NULL DEFAULT '',
            physical_address TEXT NOT NULL DEFAULT '',
            city_state_postal_code TEXT NOT NULL DEFAULT '',
            type TEXT NOT NULL DEFAULT '',
            provider_name TEXT NOT NULL DEFAULT '',
            provider_id TEXT NOT NULL DEFAULT '',
            region TEXT NOT NULL DEFAULT '',
            program_type TEXT NOT NULL DEFAULT ''
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS assessments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            assessment_name TEXT NOT NULL,
            facility_id INTEGER NOT NULL,
            facility_identifier TEXT NOT NULL DEFAULT '',
            external_system TEXT NOT NULL DEFAULT '',
            assessment_date TEXT NOT NULL,
            visit_date TEXT NOT NULL,
            inspection_type TEXT NOT NULL,
            assessor TEXT NOT NULL DEFAULT 'not implemented',
            status TEXT NOT NULL DEFAULT 'draft',
            external_case_number TEXT,
            external_inspection_id TEXT,
            contact_hours TEXT NOT NULL DEFAULT '{}',
            pqi_findings TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            modified_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    if "assessments" in existing_tables:
        _add_missing_columns(
            conn,
            "assessments",
            {
                "contact_hours": "TEXT NOT NULL DEFAULT '{}'",
                "pqi_findings": "TEXT NOT NULL DEFAULT '{}'",
            },
        )

    if "facilities" not in existing_tables or "assessments" not in existing_tables:
        log_storage_event("Ensured split facilities and assessments tables exist")

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


def get_db_connection() -> sqlite3.Connection:
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
