"""Проверка полей события."""

from datetime import datetime

from streamstats.constants import LEVELS
from streamstats.errors import (
    EmptyValueError,
    InvalidEventError,
    InvalidTimestampError,
    MissingFieldError,
)
from streamstats.models import Event


def parse_timestamp(text: str) -> datetime:
    """Разбирает ISO 8601 с обязательным часовым поясом."""
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as error:
        raise InvalidTimestampError(f"некорректная временная метка '{text}'") from error
    if parsed.tzinfo is None:
        raise InvalidTimestampError(f"временная метка '{text}' без часового пояса")
    return parsed


def _require_text(record: dict[str, object], field: str) -> str:
    """Достаёт непустую строку. «Нет поля» и «пустое значение» — разные ошибки."""
    if field not in record or record[field] is None:
        raise MissingFieldError(f"поле '{field}' отсутствует")
    value = record[field]
    if not isinstance(value, str):
        raise InvalidEventError(f"поле '{field}' должно быть строкой")
    stripped = value.strip()
    if stripped == "":
        raise EmptyValueError(f"поле '{field}' пустое")
    return stripped


def _require_message(record: dict[str, object]) -> str:
    """Достаёт message. Пустая строка допустима, отсутствие поля — нет."""
    if "message" not in record or record["message"] is None:
        raise MissingFieldError("поле 'message' отсутствует")
    value = record["message"]
    if not isinstance(value, str):
        raise InvalidEventError("поле 'message' должно быть строкой")
    return value


def event_from_mapping(record: dict[str, object]) -> Event:
    """Проверяет словарь записи и собирает событие."""
    timestamp_text = _require_text(record, "timestamp")
    level = _require_text(record, "level")
    source = _require_text(record, "source")
    message = _require_message(record)
    if level not in LEVELS:
        raise InvalidEventError(f"неизвестный уровень '{level}'")
    timestamp = parse_timestamp(timestamp_text)
    return Event(
        timestamp=timestamp,
        timestamp_text=timestamp_text,
        level=level,
        source=source,
        message=message,
    )
