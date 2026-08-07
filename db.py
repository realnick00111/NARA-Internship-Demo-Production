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
