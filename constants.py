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
    "pqi8",
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
    "pqi8": "assessments",
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

REGULATION_SET_NAME = "Evergreen Center Standards"
REGULATION_SET_VERSION = "2026.1"
REGULATION_EFFECTIVE_DATE = "2026-01-01"
CALCULATION_MODEL = "CCEEHM"
CALCULATION_MODEL_VERSION = "1.2"
CALCULATION_MODEL_PUBLICATION_DATE = "2026-05-01"
STRUCTURAL_REFERENCE_TABLE = "RWCH Conversion Table v0.9"
THRESHOLD_SET = "PQIAI Program-Type Thresholds v1.0"

INCLUDED_COMPONENTS = {
    "CONTACT_HOURS": True,
    "PQI1_5": True,
    "PQI6_8": True,
    "PQI9_10": True,
    "ATTACHMENTS_AND_NARRATIVE_NOTES": False # This is visually included as an option but not implemented.
}

PROGRAM_QUALITY_OUTCOMES = {
    "Mixed Age": {
        "High": 36,
        "High-Mid": 30,
        "Mid-Low": 20,
        "Low": 10,
    },
    "Preschool": {
        "High": 32,
        "High-Mid": 26,
        "Mid-Low": 16,
        "Low": 9,
    },
    "Infant-Toddler": {
        "High": 28,
        "High-Mid": 22,
        "Mid-Low": 12,
        "Low": 8,
    },
}
# Mixed Age High 36-40, High-Mid 30-35, Mid-Low 20-29, Low 10-19;
# Preschool High 32-36, High-Mid 26-31, Mid-Low 16-25, Low 9-15;
# Infant-Toddler High 28-32, High-Mid 22-27, Mid-Low 12-21, Low 8-11.
# These explicit lower bounds reflect the applicable indicator counts in the prototype.
# Rounds down to the nearest Threshold.

ASSESSMENTS_PER_PAGE = 8
DISABLE_DEFAULT_ASSESSMENT_FORM_VALUES = True  # Set to True to disable default values for new assessments and facility identification forms.

if not DISABLE_DEFAULT_ASSESSMENT_FORM_VALUES:
    DEFAULT_INSPECTOR_NAME = "Jordan Davis"
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
        "assigned_primary_inspector": DEFAULT_INSPECTOR_NAME,
        "inspector_name": DEFAULT_INSPECTOR_NAME,
        "inspector_identifier": "EMP-10482",
        "assessment_notes": "Routine annual monitoring visit. Structural and process quality measures collected after the on-site inspection.",
    }
else: 
    DEFAULT_INSPECTOR_NAME = ""
    DEFAULT_ASSESSMENT_FORM_VALUES = {
        "program": "",
        "facility_type": "Mixed Age",
        "inspection_type": "",
        "assessment_date": "",
        "visit_date": "",
        "external_case_number": "",
        "external_inspection_id": "",
        "local_record_name": "",
    }
    DEFAULT_FACILITY_IDENTIFICATION_FORM_VALUES = {
        "facility_name": "",
        "facility_identifier": "",
        "license_number": "",
        "provider_account_id": "",
        "program_type": "",
        "facility_type": "",
        "physical_address": "",
        "city_state_postal": "",
        "region_office": "",
        "provider_operator_name": "",
        "external_system": "",
        "external_case_number": "",
        "external_inspection_number": "",
        "visit_date": "",
        "assigned_primary_inspector": DEFAULT_INSPECTOR_NAME,
        "inspector_name": DEFAULT_INSPECTOR_NAME,
        "inspector_identifier": "",
        "assessment_notes": "",
    }

NON_PQI_FIELD_REQUIREDNESS = {
    "new-assessment": {
        "program": True,
        "facility_type": True,
        "inspection_type": True,
        "assessment_date": True,
        "visit_date": True,
        "external_case_number": False,
        "external_inspection_id": False,
        "local_record_name": False,
    },
    "facility-identification": {
        "facility_name": True,
        "facility_identifier": True,
        "license_number": False,
        "provider_account_id": False,
        "program_type": True,
        "facility_type": True,
        "physical_address": True,
        "city_state_postal": True,
        "region_office": False,
        "provider_operator_name": False,
        "external_system": True,
        "external_case_number": True,
        "external_inspection_number": False,
        "visit_date": True,
        "assigned_primary_inspector": True,
        "inspector_identifier": False,
        "assessment_notes": False,
    },
    "ch-structural-entry": {
        "to1": True,
        "to2": True,
        "ta": True,
        "nc": True,
        "th1": True,
        "th2": True,
        "density_model": True,
        "required_ratio": True,
        "ratio_source": True,
        "rwch_reference": True,
    },
}

ASSESSMENT_IMPORT_FIELD_REQUIREDNESS = {
    "assessment_name": False,
    "assessment_date": False,
    "visit_date": False,
    "program_type": False,
    "inspection_type": False,
    "facility_type": True,
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

PQI9_OBSERVATION_COUNT = 10
PQI9_OBSERVATION_DURATION_SECONDS = 2 * 60
PQI9_LIKERT_SCORE_RANGE = tuple(range(1, 5))

PQI10_OBSERVATION_COUNT = 10
PQI10_OBSERVATION_DURATION_SECONDS = 2 * 60
PQI10_LIKERT_SCORE_RANGE = tuple(range(1, 5))

# Kept for compatibility with existing PQI 9 screen imports.
PQI910_OBSERVATION_COUNT = PQI9_OBSERVATION_COUNT
PQI910_OBSERVATION_DURATION_SECONDS = PQI9_OBSERVATION_DURATION_SECONDS
PQI910_LIKERT_SCORE_RANGE = PQI9_LIKERT_SCORE_RANGE

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

PQI8_HIERARCHY = {
    "Level 1": [
        "Staff do not draw attention to logical relationships, patterns, or simple cause-and-effect connections during routines and play.",
        "Concepts are introduced without regard to children's developmental level or without connecting them to concrete experiences.",
    ],
    "Level 2": [
        "Staff occasionally point out simple logical relationships, such as sequence, comparisons, or cause and effect, during daily activities.",
        "Some concepts are introduced in ways that match children's developmental level and are supported with concrete experiences and guided discussion.",
    ],
    "Level 3": [
        "Staff regularly talk about logical relationships while children explore materials and activities that support reasoning.",
        "Children are encouraged to explain their thinking and to compare, sort, sequence, or solve simple problems with staff support.",
    ],
    "Level 4": [
        "Staff consistently build reasoning throughout the day by using children's experiences, interests, and daily events to develop logical thinking.",
        "Concepts are introduced in response to children's questions and needs, and staff support children in connecting ideas to experiences, materials, and problem solving.",
    ],
}

PQI8_SCORE_MODIFIER_REQUIREMENTS = {
    1: {"next_level": 2, "required_met": 1},
    2: {"next_level": 3, "required_met": 1},
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
