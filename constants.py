import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config.json"
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
    "import-review": "admin" + "istration",
    "audit-history": "assessments",
}

STANDALONE_SCREENS = {"login-tenant", "export-preview"}

CURRENT_ASSESSMENT_SESSION_KEY = "current_assessment_id"

with CONFIG_PATH.open(encoding="utf-8-sig") as config_file:
    CONFIG = json.load(config_file)

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
STANDALONE_SCREENS = set(STANDALONE_SCREENS)

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
DENSITY_MODEL_OPTIONS = ("Trapezoidal",)

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
    "needs review": "danger",
    "not implemented": "danger-bright",
}

globals().update(CONFIG["values"])
STANDALONE_SCREENS = set(STANDALONE_SCREENS)
FACILITY_TYPE_OPTIONS = tuple(FACILITY_TYPE_OPTIONS)
DENSITY_MODEL_OPTIONS = tuple(DENSITY_MODEL_OPTIONS)
PQI9_LIKERT_SCORE_RANGE = tuple(PQI9_LIKERT_SCORE_RANGE)
PQI10_LIKERT_SCORE_RANGE = tuple(PQI10_LIKERT_SCORE_RANGE)
PQI910_LIKERT_SCORE_RANGE = tuple(PQI910_LIKERT_SCORE_RANGE)
PQI4_BAND_MAPPING = {float(key): value for key, value in PQI4_BAND_MAPPING.items()}
PQI6_SCORE_MODIFIER_REQUIREMENTS = {int(key): value for key, value in PQI6_SCORE_MODIFIER_REQUIREMENTS.items()}
PQI7_SCORE_MODIFIER_REQUIREMENTS = {int(key): value for key, value in PQI7_SCORE_MODIFIER_REQUIREMENTS.items()}
PQI8_SCORE_MODIFIER_REQUIREMENTS = {int(key): value for key, value in PQI8_SCORE_MODIFIER_REQUIREMENTS.items()}
PQI_BAND_MAPPING = {
    tuple(int(value) for value in key.removeprefix("tuple:").split(",")): band
    for key, band in PQI_BAND_MAPPING.items()
}