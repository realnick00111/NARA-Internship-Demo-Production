from pathlib import Path

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
