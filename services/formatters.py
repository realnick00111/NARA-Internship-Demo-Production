from datetime import datetime
from difflib import SequenceMatcher
from decimal import Decimal, ROUND_HALF_UP

from constants import (
    PQI4_BAND_MAPPING,
    PQI5_QUESTION_POINTS,
    PQI6_SCORE_MODIFIER_REQUIREMENTS,
    PQI7_SCORE_MODIFIER_REQUIREMENTS,
    PQI8_SCORE_MODIFIER_REQUIREMENTS,
    PQI_BAND_MAPPING,
    STATUS_CLASS_MAP,
)


def normalize_text(value: str | None) -> str:
    return " ".join(str(value or "").casefold().split())


def round_percentage_half_up(value: float | int) -> int:
    if value is None:
        raise TypeError("value cannot be None")
    return int(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def format_date_label(date_value: str | None) -> str:
    value = str(date_value or "").strip()
    if not value:
        return "not available"

    for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
        try:
            parsed = datetime.strptime(value, fmt)
            return parsed.strftime("%b %d, %Y")
        except ValueError:
            continue

    return value


def format_timestamp_label(timestamp_value: str | None) -> str:
    value = str(timestamp_value or "").strip()
    if not value:
        return "not available"

    parsed_value: datetime | None = None
    for candidate_format in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S.%f",
    ):
        try:
            parsed_value = datetime.strptime(value, candidate_format)
            break
        except ValueError:
            continue

    if parsed_value is None:
        try:
            parsed_value = datetime.fromisoformat(value)
        except ValueError:
            return value

    today = datetime.now().date()
    if parsed_value.date() == today:
        return f"Today, {parsed_value.strftime('%I:%M %p').lstrip('0')}"

    if parsed_value.date().toordinal() == today.toordinal() - 1:
        return f"Yesterday, {parsed_value.strftime('%I:%M %p').lstrip('0')}"

    return parsed_value.strftime("%b %d, %I:%M %p").replace(" 0", " ")


def get_status_chip_class(status_value: str | None) -> str:
    normalized = normalize_text(status_value)
    return STATUS_CLASS_MAP.get(normalized, "neutral")


def get_status_label(status_value: str | None) -> str:
    normalized = normalize_text(status_value)
    if normalized == "needs review":
        return "Needs updates"
    return str(status_value or "not available").strip().title()


def _calculate_band_score_from_percentage(percentage: float) -> int | None:
    for (lower_bound, upper_bound), band in sorted(PQI_BAND_MAPPING.items(), key=lambda item: item[1]):
        if lower_bound <= percentage <= upper_bound:
            return band

    return None


def calculate_pqi1_score(certified_teaching_staff: object, total_teaching_staff: object) -> int | None:
    try:
        certified_count = int(certified_teaching_staff)
        total_count = int(total_teaching_staff)
    except (TypeError, ValueError):
        return None

    if certified_count < 0 or total_count <= 0 or certified_count > total_count:
        return None

    percentage = (certified_count / total_count) * 100
    return _calculate_band_score_from_percentage(percentage)


def normalize_yes_no(value: object) -> str | None:
    if value is None:
        return None

    text = str(value).strip().casefold()
    if text == "yes":
        return "yes"
    if text == "no":
        return "no"
    if text == "":
        return None
    return None


def calculate_pqi2_score(responses: list[object]) -> int | None:
    normalized_responses = [normalize_yes_no(value) for value in responses]
    if any(response is None for response in normalized_responses):
        return None

    if not normalized_responses:
        return None

    yes_count = sum(1 for response in normalized_responses if response == "yes")
    percentage = (yes_count / len(normalized_responses)) * 100
    return _calculate_band_score_from_percentage(percentage)


def calculate_pqi4_score(responses: list[object]) -> int | None:
    normalized_responses = [normalize_yes_no(value) for value in responses]
    if not normalized_responses or any(response is None for response in normalized_responses):
        return None

    percentage = round((sum(response == "yes" for response in normalized_responses) / len(normalized_responses)) * 100, 2)
    return PQI4_BAND_MAPPING.get(percentage)


def calculate_pqi5_points(responses: list[object]) -> tuple[int, int, int] | None:
    normalized_responses = [normalize_yes_no(value) for value in responses]
    if len(normalized_responses) != len(PQI5_QUESTION_POINTS) or any(response is None for response in normalized_responses):
        return None

    base_points = sum(
        points for points, response in zip(PQI5_QUESTION_POINTS[:-1], normalized_responses[:-1]) if response == "yes"
    )
    bonus_point = PQI5_QUESTION_POINTS[-1] if normalized_responses[-1] == "yes" else 0
    return base_points, bonus_point, base_points + bonus_point


def calculate_pqi6_score_modifier(score: int, responses: dict[str, list[bool] | list[object]] | None) -> str:
    if score not in PQI6_SCORE_MODIFIER_REQUIREMENTS:
        return ""

    if not isinstance(responses, dict):
        return ""

    modifier_rule = PQI6_SCORE_MODIFIER_REQUIREMENTS[score]
    next_level = str(modifier_rule["next_level"])
    next_level_responses = responses.get(next_level, [])
    if not isinstance(next_level_responses, list):
        return ""

    relevant_items = next_level_responses[: len(next_level_responses)]
    met_count = sum(1 for value in relevant_items if bool(value))
    required_met = modifier_rule["required_met"]
    return "+" if met_count >= required_met else ""


def format_pqi6_score(score: int, modifier: str = "") -> str:
    if score <= 0:
        return "0"
    return f"{score}{modifier}" if modifier else str(score)


def calculate_pqi7_score_modifier(score: int, responses: dict[str, list[bool] | list[object]] | None) -> str:
    if score not in PQI7_SCORE_MODIFIER_REQUIREMENTS or not isinstance(responses, dict):
        return ""

    modifier_rule = PQI7_SCORE_MODIFIER_REQUIREMENTS[score]
    next_level_responses = responses.get(str(modifier_rule["next_level"]), [])
    if not isinstance(next_level_responses, list):
        return ""

    met_count = sum(1 for value in next_level_responses if bool(value))
    return "+" if met_count >= modifier_rule["required_met"] else ""


def format_pqi7_score(score: int, modifier: str = "") -> str:
    if score <= 0:
        return "0"
    return f"{score}{modifier}" if modifier else str(score)


def calculate_pqi8_score_modifier(score: int, responses: dict[str, list[bool] | list[object]] | None) -> str:
    if score not in PQI8_SCORE_MODIFIER_REQUIREMENTS or not isinstance(responses, dict):
        return ""

    modifier_rule = PQI8_SCORE_MODIFIER_REQUIREMENTS[score]
    next_level_responses = responses.get(str(modifier_rule["next_level"]), [])
    if not isinstance(next_level_responses, list):
        return ""

    met_count = sum(1 for value in next_level_responses if bool(value))
    return "+" if met_count >= modifier_rule["required_met"] else ""


def format_pqi8_score(score: int, modifier: str = "") -> str:
    if score <= 0:
        return "0"
    return f"{score}{modifier}" if modifier else str(score)


def calculate_pqi3_score(records: list[dict]) -> int | None:
    if len(records) != 10:
        return None

    positive_count = sum(1 for record in records if record.get("positive") is True)
    return _calculate_band_score_from_percentage((positive_count / 10) * 100)


def names_are_similar(left: str | None, right: str | None) -> bool:
    left_text = normalize_text(left)
    right_text = normalize_text(right)

    if not left_text or not right_text:
        return False

    if left_text == right_text:
        return True

    return SequenceMatcher(None, left_text, right_text).ratio() >= 0.82
