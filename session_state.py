from flask import session

from constants import CURRENT_ASSESSMENT_SESSION_KEY


def set_current_assessment(assessment_id: int) -> None:
    session[CURRENT_ASSESSMENT_SESSION_KEY] = assessment_id


def get_current_assessment() -> int | None:
    return session.get(CURRENT_ASSESSMENT_SESSION_KEY)


def clear_current_assessment() -> None:
    session.pop(CURRENT_ASSESSMENT_SESSION_KEY, None)
