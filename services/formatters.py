from datetime import datetime
from difflib import SequenceMatcher

from constants import PQI_BAND_MAPPING, STATUS_CLASS_MAP


def normalize_text(value: str | None) -> str:
    return " ".join(str(value or "").casefold().split())


def format_date_label(date_value: str | None) -> str:
    value = str(date_value or "").strip()
    if not value:
        return "not implemented"

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
        return "not implemented"

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


def calculate_pqi1_score(certified_teaching_staff: object, total_teaching_staff: object) -> int | None:
    try:
        certified_count = int(certified_teaching_staff)
        total_count = int(total_teaching_staff)
    except (TypeError, ValueError):
        return None

    if certified_count < 0 or total_count <= 0 or certified_count > total_count:
        return None

    percentage = (certified_count / total_count) * 100
    for (lower_bound, upper_bound), band in sorted(PQI_BAND_MAPPING.items(), key=lambda item: item[1]):
        if lower_bound <= percentage <= upper_bound:
            return band

    return None


def names_are_similar(left: str | None, right: str | None) -> bool:
    left_text = normalize_text(left)
    right_text = normalize_text(right)

    if not left_text or not right_text:
        return False

    if left_text == right_text:
        return True

    return SequenceMatcher(None, left_text, right_text).ratio() >= 0.82
