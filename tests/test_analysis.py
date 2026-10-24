"""Тесты проверки событий и накопления статистики."""

from collections.abc import Iterator
from pathlib import Path

import pytest

from streamstats.analysis import (
    Stats,
    collect_stats,
    event_from_mapping,
    parse_timestamp,
)
from streamstats.errors import (
    EmptyValueError,
    InvalidTimestampError,
    MissingFieldError,
    StreamStatsError,
    UnsupportedFormatError,
)
from streamstats.filters import filter_events
from streamstats.models import Event


def make_event(text: str, level: str, source: str, message: str = "ok") -> Event:
    """Собирает событие для тестов статистики."""
    return Event(
        timestamp=parse_timestamp(text),
        timestamp_text=text,
        level=level,
        source=source,
        message=message,
    )


def test_missing_field_is_not_the_same_as_empty_value() -> None:
    """Отсутствующее поле и пустая строка — разные классы ошибок."""
    base = {"level": "INFO", "source": "api", "message": "привет"}
    with pytest.raises(MissingFieldError):
        event_from_mapping(base)
    empty_timestamp = dict(base)
    empty_timestamp["timestamp"] = ""
    with pytest.raises(EmptyValueError):
        event_from_mapping(empty_timestamp)
    null_source = {
        "timestamp": "2026-10-07T12:00:00+00:00",
        "level": "INFO",
        "source": None,
        "message": "привет",
    }
    with pytest.raises(MissingFieldError):
        event_from_mapping(null_source)
    empty_source = {
        "timestamp": "2026-10-07T12:00:00+00:00",
        "level": "INFO",
        "source": "   ",
        "message": "привет",
    }
    with pytest.raises(EmptyValueError):
        event_from_mapping(empty_source)


def test_naive_timestamp_is_rejected_and_zulu_matches_utc() -> None:
    """Время без пояса не годится. Z = +00:00."""
    with pytest.raises(InvalidTimestampError):
        event_from_mapping(
            {
                "timestamp": "2026-10-07T12:00:00",
                "level": "INFO",
                "source": "api",
                "message": "x",
            }
        )
    zulu = parse_timestamp("2026-10-07T09:00:00Z")
    utc = parse_timestamp("2026-10-07T09:00:00+00:00")
    assert zulu == utc


def test_timestamps_follow_the_instant_not_the_text(tmp_path: Path) -> None:
    """12:00+03 раньше, чем 10:00+00."""
    path = tmp_path / "time.csv"
    path.write_text(
        "timestamp,level,source,message\n"
        "2026-10-07T12:00:00+03:00,INFO,loader,local\n"
        "2026-10-07T09:00:00+00:00,INFO,loader,same\n"
        "2026-10-07T10:00:00+00:00,INFO,loader,later\n",
        encoding="utf-8",
    )
    stats = collect_stats([path], "csv", skip_invalid=False)
    assert stats.first_text == "2026-10-07T12:00:00+03:00"
    assert stats.last_text == "2026-10-07T10:00:00+00:00"


def test_empty_file_gives_zero_stats(tmp_path: Path) -> None:
    """Пустой CSV и пустой JSONL дают нули и пустые метки времени."""
    csv_path = tmp_path / "empty.csv"
    jsonl_path = tmp_path / "empty.jsonl"
    csv_path.write_text("", encoding="utf-8")
    jsonl_path.write_text("", encoding="utf-8")
    csv_stats = collect_stats([csv_path], "csv", skip_invalid=False)
    jsonl_stats = collect_stats([jsonl_path], "jsonl", skip_invalid=False)
    assert csv_stats.total_events == 0
    assert jsonl_stats.total_events == 0
    assert csv_stats.first_text is None
    assert csv_stats.last_text is None
    assert csv_stats.by_level["ERROR"] == 0
    assert csv_stats.skipped_invalid == 0


def test_broken_csv_stops_by_default(tmp_path: Path) -> None:
    """Без --skip-invalid плохая CSV-строка останавливает разбор."""
    path = tmp_path / "broken.csv"
    path.write_text(
        "timestamp,level,source,message\n"
        "2026-10-07T12:00:00+00:00,INFO,loader,ok\n"
        "2026-10-07T13:00:00+00:00,INFO,,bad\n"
        "2026-10-07T14:00:00+00:00,ERROR,loader,after\n",
        encoding="utf-8",
    )
    with pytest.raises(StreamStatsError) as caught:
        collect_stats([path], "csv", skip_invalid=False)
    message = str(caught.value)
    assert path.name in message
    assert ":3:" in message


def test_broken_csv_skip_invalid_continues(tmp_path: Path) -> None:
    """С пропуском плохая CSV-строка не мешает соседним событиям."""
    path = tmp_path / "broken.csv"
    path.write_text(
        "timestamp,level,source,message\n"
        "2026-10-07T12:00:00+00:00,INFO,loader,ok\n"
        "2026-10-07T13:00:00+00:00,INFO,,bad\n"
        "2026-10-07T14:00:00+00:00,ERROR,loader,after\n",
        encoding="utf-8",
    )
    stats = collect_stats([path], "csv", skip_invalid=True)
    assert stats.skipped_invalid == 1
    assert stats.total_events == 2
    assert stats.by_level["ERROR"] == 1
    assert stats.by_level["INFO"] == 1


def test_broken_jsonl_stops_by_default(tmp_path: Path) -> None:
    """Без пропуска номер ошибки - это номер строки исходного JSONL."""
    path = tmp_path / "broken.jsonl"
    path.write_text(
        '{"timestamp":"2026-10-07T12:00:00+00:00","level":"INFO",'
        '"source":"api","message":"ok"}\n'
        "not-json\n"
        '{"timestamp":"2026-10-07T13:00:00+00:00","level":"ERROR",'
        '"source":"api","message":"after"}\n',
        encoding="utf-8",
    )
    with pytest.raises(StreamStatsError) as caught:
        collect_stats([path], "jsonl", skip_invalid=False)
    message = str(caught.value)
    assert path.name in message
    assert ":2:" in message


def test_broken_jsonl_skip_invalid_continues(tmp_path: Path) -> None:
    """С пропуском следующая корректная JSONL-строка всё равно учитывается."""
    path = tmp_path / "broken.jsonl"
    path.write_text(
        '{"timestamp":"2026-10-07T12:00:00+00:00","level":"INFO",'
        '"source":"api","message":"ok"}\n'
        "not-json\n"
        '{"timestamp":"2026-10-07T13:00:00+00:00","level":"ERROR",'
        '"source":"api","message":"after"}\n',
        encoding="utf-8",
    )
    stats = collect_stats([path], "jsonl", skip_invalid=True)
    assert stats.skipped_invalid == 1
    assert stats.total_events == 2
    assert stats.by_level["ERROR"] == 1


def test_several_files_are_merged(tmp_path: Path) -> None:
    """Счётчики и границы времени общие для нескольких файлов."""
    first = tmp_path / "a.csv"
    second = tmp_path / "b.csv"
    first.write_text(
        "timestamp,level,source,message\n2026-10-07T10:00:00+00:00,INFO,api,one\n",
        encoding="utf-8",
    )
    second.write_text(
        "timestamp,level,source,message\n2026-10-07T08:00:00+00:00,ERROR,db,two\n",
        encoding="utf-8",
    )
    stats = collect_stats([first, second], "csv", skip_invalid=False)
    assert stats.total_events == 2
    assert stats.by_source["api"] == 1
    assert stats.by_source["db"] == 1
    assert stats.by_level["ERROR"] == 1
    assert stats.first_text == "2026-10-07T08:00:00+00:00"
    assert stats.last_text == "2026-10-07T10:00:00+00:00"
    assert stats.error_by_source["db"] == 1


def test_unicode_source_and_message_are_preserved(tmp_path: Path) -> None:
    """Кириллица в источнике и тексте не портится."""
    path = tmp_path / "unicode.jsonl"
    path.write_text(
        '{"timestamp":"2026-10-07T12:00:00+03:00","level":"ERROR",'
        '"source":"загрузчик","message":"Ошибка: нет доступа"}\n',
        encoding="utf-8",
    )
    stats = collect_stats([path], "jsonl", skip_invalid=False)
    assert stats.total_events == 1
    assert stats.by_source["загрузчик"] == 1
    assert stats.first_text == "2026-10-07T12:00:00+03:00"


def test_top_error_sources_break_ties_by_name() -> None:
    """Top-5 берёт только ERROR и CRITICAL, при равенстве - сортировка по алфавиту."""
    stats = Stats()
    rows = [
        ("b", "ERROR"),
        ("a", "CRITICAL"),
        ("b", "ERROR"),
        ("a", "ERROR"),
        ("c", "CRITICAL"),
        ("c", "CRITICAL"),
        ("d", "ERROR"),
        ("d", "ERROR"),
        ("e", "ERROR"),
        ("e", "ERROR"),
        ("f", "ERROR"),
        ("warn", "WARNING"),
        ("warn", "WARNING"),
        ("warn", "WARNING"),
    ]
    for source, level in rows:
        stats.add(make_event("2026-10-07T12:00:00+00:00", level, source))
    top = stats.top_error_sources()
    assert top == [("a", 2), ("b", 2), ("c", 2), ("d", 2), ("e", 2)]
    assert stats.by_source["warn"] == 3
    assert "warn" not in stats.error_by_source


def test_unsupported_format_is_its_own_error(tmp_path: Path) -> None:
    """Неизвестный формат — UnsupportedFormatError."""
    path = tmp_path / "notes.txt"
    path.write_text("hello\n", encoding="utf-8")
    with pytest.raises(UnsupportedFormatError):
        collect_stats([path], "xml", skip_invalid=False)


def test_examples_csv_has_expected_totals() -> None:
    """Учебный examples/events.csv даёт стабильные итоги."""
    path = Path(__file__).resolve().parents[1] / "examples" / "events.csv"
    stats = collect_stats([path], "csv", skip_invalid=False)
    assert stats.total_events == 5
    assert stats.by_source["загрузчик"] == 1
    assert stats.by_level["CRITICAL"] == 1
    assert stats.error_by_source["api"] == 2
    assert stats.first_text == "2026-10-07T12:00:00+03:00"
    assert stats.last_text == "2026-10-07T11:00:00+00:00"


def test_level_filter_does_not_pull_events_ahead() -> None:
    """Фильтр забирает следующее событие только когда его просят."""
    pulled = {"count": 0}
    events = [
        make_event("2026-10-07T10:00:00+00:00", "INFO", "a"),
        make_event("2026-10-07T11:00:00+00:00", "ERROR", "b"),
        make_event("2026-10-07T12:00:00+00:00", "ERROR", "c"),
    ]

    def source() -> Iterator[Event]:
        """Считает, сколько событий уже отдали наружу."""
        for event in events:
            pulled["count"] += 1
            yield event

    found = next(filter_events(source(), level="ERROR"))
    assert found.source == "b"
    assert pulled["count"] == 2


def test_time_filter_bounds_are_inclusive(tmp_path: Path) -> None:
    """--since и --until оставляют события на самих границах."""
    path = tmp_path / "span.csv"
    path.write_text(
        "timestamp,level,source,message\n"
        "2026-10-07T10:00:00+00:00,INFO,api,early\n"
        "2026-10-07T11:00:00+00:00,ERROR,api,edge\n"
        "2026-10-07T12:00:00+00:00,INFO,api,late\n",
        encoding="utf-8",
    )
    since = parse_timestamp("2026-10-07T11:00:00+00:00")
    until = parse_timestamp("2026-10-07T11:00:00+00:00")
    stats = collect_stats(
        [path],
        "csv",
        skip_invalid=False,
        since=since,
        until=until,
    )
    assert stats.total_events == 1
    assert stats.by_level["ERROR"] == 1
