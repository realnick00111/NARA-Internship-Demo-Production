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
    "pqi1",
    "pqi3-sample",
    "pqi3",
    "pqi6-8-hierarchy",
    "pqi7",
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
    "pqi1": "assessments",
    "pqi3-sample": "assessments",
    "pqi3": "assessments",
    "pqi6-8-hierarchy": "assessments",
    "pqi7": "assessments",
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
    "facility_type": "Mixed Age",
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
    "facility_type": "Mixed Age",
    "physical_address": "1250 Cedar Avenue",
    "city_state_postal": "Olympia, WA 98501",
    "region_office": "Region 3 - South Sound",
    "provider_operator_name": "Sunrise Learning LLC",
    "external_system": "Compass",
    "external_case_number": "CMP-2026-004182",
    "external_inspection_number": "INS-2026-0714-22",
    "visit_date": "2026-07-14",
    "assigned_primary_inspector": "Jordan Davis",
    "inspector_name": "Jordan Davis",
    "inspector_identifier": "EMP-10482",
    "assessment_notes": "Routine annual monitoring visit. Structural and process quality measures collected after the on-site inspection.",
}

FACILITY_TYPE_OPTIONS = ("Mixed Age", "Preschool", "Infant-Toddler")

FACILITY_TYPE_PQI_MAPPING = {
    "Mixed Age": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
    "Preschool": [1, 2, 3, 4, 5, 6, 8, 9, 10],
    "Infant-Toddler": [1, 2, 3, 4, 5, 7, 9, 10],
}

PQI2_ENVIRONMENT_QUESTIONS = [
    "Co-teaching is evident.",
    "Children are viewed as competent learners and can access materials independently.",
    "Authentic and meaningful materials are used with children.",
    "Children are provided with meaningful choices.",
    "Children's work, art and photos are displayed respectfully.",
    "Family photos are displayed in the early learning program.",
    "Documentation of learning is displayed and discusses holistic development.",
    "Environment reflects the culture and beliefs of the children, families and staff.",
    "Variety of books and other print materials are available throughout the classroom.",
    "A variety of writing materials are accessible to children most of the time.",
    "There is evidence of the children's interests and projects in the classroom.",
]

PQI4_STAFF_FAMILY_OPPORTUNITIES_QUESTIONS = [
    "The program provides communication, education, and informational materials and opportunities for families that are delivered in a way that meets their diverse needs.",
    "The program communicates with families using different modes of communication, and at least one mode promotes two-way communication.",
    "The program demonstrates respect and engages in ongoing two-way communication. The program respects each family's strengths, choices, and goals for their children.",
]

PQI4_BAND_MAPPING = {
    0: 1,
    33.33: 2,
    66.67: 3,
    100: 4,
}

PQI5_CHILD_PROGRESS_QUESTIONS = [
    "The program holds qualifying conferences with families at least twice yearly.",
    "The program provides a written developmental-progress report for each child.",
    "The program engages in culturally and linguistically appropriate interactions with children and families.",
]

# Points awarded per question, in the same order as PQI5_CHILD_PROGRESS_QUESTIONS; the last question is the bonus point.
PQI5_QUESTION_POINTS = [2, 1, 1]

PQI3_RECORD_COUNT = 10

PQI6_HIERARCHY = {
    "Foundational practice": [
        "Staff respond when children initiate communication",
        "Staff use respectful and age-appropriate language",
        "Children have regular opportunities to communicate",
    ],
    "Consistent practice": [
        "Staff extend children's ideas through follow-up questions",
        "Conversations include more than one exchange",
        "Language is adapted to individual developmental levels",
        "Visual or contextual supports are used when needed",
    ],
    "Advanced practice": [
        "Staff intentionally introduce new vocabulary",
        "Children are encouraged to explain reasoning",
        "Staff connect current discussion to prior learning",
        "Peer-to-peer dialogue is intentionally supported",
    ],
    "Sustained exemplary practice": [
        "Staff facilitate extended, child-led conversations that build on children's ideas",
        "Language and interaction strategies consistently support complex thinking",
        "Children independently use rich language with adults and peers",
        "Staff use observation evidence to refine language and interaction practices",
    ],
}

PQI6_SCORE_MODIFIER_REQUIREMENTS = {
    1: {"next_level": 2, "required_met": 2},
    2: {"next_level": 3, "required_met": 1},
    3: {"next_level": 4, "required_met": 1},
}

PQI7_HIERARCHY = {
    "Level 1": [
        "Staff never initiate turn-taking conversations with children",
        "Staff questions are often not appropriate for children, or no questions are asked",
        "Staff respond negatively when children cannot answer questions",
    ],
    "Level 2": [
        "Staff sometimes initiate conversations with children",
        "Staff sometimes ask children appropriate questions and wait for the child to respond",
        "Staff respond neutrally or positively to children who cannot answer questions and questions asked are sometimes meaningful to children",
    ],
    "Level 3": [
        "Staff initiate engaging conversations with children throughout the observation",
        "Staff often personalize questions and or conversations for individual children",
        "Staff often pay attention to children's questions, verbal or nonverbal, and answer in a satisfying manner for the child",
        "Staff ask questions in which children show interest in answering",
    ],
    "Level 4": [
        "Staff frequently have turn-taking conversations with children throughout the observations and use many appropriate questions during both play and routines",
        "Staff ask children appropriate questions, wait a reasonable time for child response, and then answer if needed",
    ],
}

PQI7_SCORE_MODIFIER_REQUIREMENTS = {
    1: {"next_level": 2, "required_met": 2},
    2: {"next_level": 3, "required_met": 2},
    3: {"next_level": 4, "required_met": 1},
}

PQI_BAND_MAPPING = {
    (0, 25): 1,
    (26, 50): 2,
    (51, 75): 3,
    (76, 100): 4,
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
