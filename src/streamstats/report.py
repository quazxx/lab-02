"""Сборка отчёта из уже посчитанных итогов."""

import json
from dataclasses import dataclass
from pathlib import Path

from streamstats.analysis import Stats
from streamstats.errors import StreamStatsError


@dataclass
class ReportData:
    """Итоги для JSON."""

    total_events: int
    by_level: dict[str, int]
    by_source: dict[str, int]
    top_error_sources: list[tuple[str, int]]
    first_timestamp: str | None
    last_timestamp: str | None
    skipped_invalid: int


def build_report(stats: Stats) -> ReportData:
    """Перекладывает счётчики в отчёт."""
    by_source: dict[str, int] = {}
    for source in sorted(stats.by_source):
        by_source[source] = stats.by_source[source]
    return ReportData(
        total_events=stats.total_events,
        by_level=dict(stats.by_level),
        by_source=by_source,
        top_error_sources=stats.top_error_sources(),
        first_timestamp=stats.first_text,
        last_timestamp=stats.last_text,
        skipped_invalid=stats.skipped_invalid,
    )


def _json_payload(data: ReportData) -> dict[str, object]:
    """Собирает словарь с фиксированным порядком ключей."""
    by_level: dict[str, object] = {}
    for level, count in data.by_level.items():
        by_level[level] = count
    by_source: dict[str, object] = {}
    for source, count in data.by_source.items():
        by_source[source] = count
    top: list[dict[str, object]] = []
    for source, count in data.top_error_sources:
        item: dict[str, object] = {"source": source, "count": count}
        top.append(item)
    return {
        "total_events": data.total_events,
        "by_level": by_level,
        "by_source": by_source,
        "top_error_sources": top,
        "first_timestamp": data.first_timestamp,
        "last_timestamp": data.last_timestamp,
        "skipped_invalid": data.skipped_invalid,
    }


def write_json_report(data: ReportData, path: Path) -> None:
    """Записывает JSON-отчёт."""
    text = json.dumps(_json_payload(data), ensure_ascii=False, indent=2)
    try:
        path.write_text(text + "\n", encoding="utf-8")
    except OSError as error:
        raise StreamStatsError(f"не удалось записать отчёт {path}: {error}") from error
