from pathlib import Path

from flask import abort, render_template, render_template_string
from markupsafe import Markup

from constants import (
    NAV_BY_SCREEN,
    PARTIALS_DIR,
    PQI_BAND_MAPPING,
    PQI910_LIKERT_SCORE_RANGE,
    PQI910_OBSERVATION_COUNT,
    PQI910_OBSERVATION_DURATION_SECONDS,
    SCREENS_DIR,
    SCREEN_ORDER,
    STANDALONE_SCREENS,
)
from services.screen_contexts import (
    build_assessment_list_context,
    build_assessment_progress_context,
    build_contact_hours_context,
    build_dashboard_context,
    build_duplicate_warning_html,
    build_facility_identification_context,
    build_pqi1_context,
    build_pqi3_context,
    build_pqi6_context,
    build_pqi7_context,
    build_pqi8_context,
    build_pqi910_context,
    build_new_assessment_context,
    get_current_assessment_row,
    get_assessment_label,
)


def read_fragment(fragment_path: Path) -> str:
    return fragment_path.read_text(encoding="utf-8")


def build_pqi1_band_rows() -> list[dict[str, int]]:
    return [
        {"min": lower_bound, "max": upper_bound, "band": band}
        for (lower_bound, upper_bound), band in sorted(PQI_BAND_MAPPING.items(), key=lambda item: item[1])
    ]


def render_screen_section(screen_id: str) -> str:
    screen_path = SCREENS_DIR / f"{screen_id}.html"
    content = read_fragment(screen_path)

    if screen_id == "facility-identification":
        content = render_template_string(
            content,
            duplicate_warning=build_duplicate_warning_html(),
            **build_facility_identification_context(),
        )
    elif screen_id == "agency-dashboard":
        content = render_template_string(content, **build_dashboard_context())
    elif screen_id == "assessment-list":
        content = render_template_string(content, **build_assessment_list_context())
    elif screen_id == "pqi-findings-entry":
        content = render_template_string(content, **build_pqi1_context(), pqi1_band_rows=build_pqi1_band_rows())
    elif screen_id == "ch-structural-entry":
        content = render_template_string(content, **build_contact_hours_context())
    elif screen_id == "new-assessment":
        content = render_template_string(content, **build_new_assessment_context())
    elif screen_id == "assessment-progress":
        content = render_template_string(content, **build_assessment_progress_context())
    elif screen_id == "pqi1":
        content = render_template_string(content, **build_pqi1_context(), pqi1_band_rows=build_pqi1_band_rows())
    elif screen_id == "pqi3-sample":
        content = render_template_string(content, **build_pqi3_context(preview=True), pqi1_band_rows=build_pqi1_band_rows())
    elif screen_id == "pqi3":
        content = render_template_string(content, **build_pqi3_context(), pqi1_band_rows=build_pqi1_band_rows())
    elif screen_id == "pqi6-8-hierarchy":
        content = render_template_string(content, **build_pqi6_context())
    elif screen_id == "pqi7":
        content = render_template_string(content, **build_pqi7_context())
    elif screen_id == "pqi8":
        content = render_template_string(content, **build_pqi8_context())
    elif screen_id == "pqi9-10-timed":
        content = render_template_string(content, **build_pqi910_context())

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
