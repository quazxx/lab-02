"""Проверка событий и накопление статистики за один проход."""

import logging
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

from streamstats.constants import (
    ERROR_LEVELS,
    FORMAT_CSV,
    FORMAT_JSONL,
    LEVELS,
    LOGGER_NAME,
    SUPPORTED_FORMATS,
    TOP_ERROR_SOURCE_LIMIT,
)
from streamstats.errors import (
    EmptyValueError,
    InvalidEventError,
    InvalidTimestampError,
    MissingFieldError,
    StreamStatsError,
    UnsupportedFormatError,
)
from streamstats.filters import filter_events
from streamstats.models import Event
from streamstats.parsers import iter_csv_records, iter_jsonl_lines, parse_jsonl_line


def get_logger() -> logging.Logger:
    """Возвращает логгер пакета."""
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        logger.addHandler(logging.NullHandler())
    return logger


def ensure_format(file_format: str) -> None:
    """Проверяет, что формат равен csv или jsonl."""
    if file_format not in SUPPORTED_FORMATS:
        raise UnsupportedFormatError(f"неподдерживаемый формат '{file_format}'")


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
    """Достаёт непустую строку."""
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
    """Достаёт message."""
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


def _error_rank(item: tuple[str, int]) -> tuple[int, str]:
    """Ключ сортировки: больше ошибок выше, при равенстве сортировка по алфавиту."""
    source, count = item
    return (-count, source)


class Stats:
    """Текущие итоги."""

    def __init__(self) -> None:
        """Обнуляет счётчики."""
        self.total_events = 0
        self.by_level: dict[str, int] = {}
        for level in LEVELS:
            self.by_level[level] = 0
        self.by_source: dict[str, int] = {}
        self.error_by_source: dict[str, int] = {}
        self.first_dt: datetime | None = None
        self.first_text: str | None = None
        self.last_dt: datetime | None = None
        self.last_text: str | None = None
        self.skipped_invalid = 0

    def add(self, event: Event) -> None:
        """Учитывает одно корректное событие."""
        self.total_events += 1
        self.by_level[event.level] += 1
        previous = self.by_source.get(event.source, 0)
        self.by_source[event.source] = previous + 1
        if event.level in ERROR_LEVELS:
            previous_errors = self.error_by_source.get(event.source, 0)
            self.error_by_source[event.source] = previous_errors + 1
        if self.first_dt is None or event.timestamp < self.first_dt:
            self.first_dt = event.timestamp
            self.first_text = event.timestamp_text
        if self.last_dt is None or event.timestamp > self.last_dt:
            self.last_dt = event.timestamp
            self.last_text = event.timestamp_text

    def add_skipped(self) -> None:
        """Увеличивает число пропущенных повреждённых строк."""
        self.skipped_invalid += 1

    def top_error_sources(self) -> list[tuple[str, int]]:
        """Возвращает не больше пяти источников с событиями ERROR и CRITICAL."""
        pairs: list[tuple[str, int]] = []
        for source, count in self.error_by_source.items():
            if count > 0:
                pairs.append((source, count))
        pairs.sort(key=_error_rank)
        return pairs[:TOP_ERROR_SOURCE_LIMIT]


def _fail_or_skip(
    path: Path,
    line_number: int,
    error: StreamStatsError,
    stats: Stats,
    skip_invalid: bool,
) -> None:
    """Пропускает повреждённую строку или останавливает разбор."""
    message = f"{path}:{line_number}: {error}"
    if skip_invalid:
        get_logger().warning(message)
        stats.add_skipped()
        return
    raise StreamStatsError(message) from error


def _events_from_file(
    path: Path,
    file_format: str,
    stats: Stats,
    skip_invalid: bool,
) -> Iterator[Event]:
    """Отдаёт корректные события одного файла по одному."""
    if file_format == FORMAT_JSONL:
        for line_number, line in iter_jsonl_lines(path):
            try:
                record = parse_jsonl_line(line)
                if record is None:
                    continue
                yield event_from_mapping(record)
            except StreamStatsError as error:
                _fail_or_skip(path, line_number, error, stats, skip_invalid)
        return
    if file_format == FORMAT_CSV:
        for line_number, record in iter_csv_records(path):
            try:
                yield event_from_mapping(record)
            except StreamStatsError as error:
                _fail_or_skip(path, line_number, error, stats, skip_invalid)
        return
    raise UnsupportedFormatError(f"неподдерживаемый формат '{file_format}'")


def collect_stats(
    paths: list[Path],
    file_format: str,
    skip_invalid: bool,
    level: str | None = None,
    source: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
) -> Stats:
    """Читает файлы по очереди и копит одну общую статистику."""
    ensure_format(file_format)
    stats = Stats()
    logger = get_logger()
    for path in paths:
        if not path.is_file():
            raise StreamStatsError(f"файл не найден: {path}")
        logger.info(f"Начало чтения файла {path}")
        try:
            events = _events_from_file(path, file_format, stats, skip_invalid)
            filtered = filter_events(
                events,
                level=level,
                source=source,
                since=since,
                until=until,
            )
            for event in filtered:
                stats.add(event)
        except OSError as error:
            raise StreamStatsError(
                f"не удалось прочитать файл {path}: {error}"
            ) from error
        logger.info(f"Файл {path} обработан")
    logger.info(
        f"Готово: событий {stats.total_events}, пропущено {stats.skipped_invalid}",
    )
    return stats
