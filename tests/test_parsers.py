"""Тесты потоковых парсеров CSV и JSONL."""

from pathlib import Path

import pytest

from streamstats.errors import InvalidEventError
from streamstats.parsers import iter_csv_records, iter_jsonl_lines, parse_jsonl_line


def test_csv_parser_reads_quoted_comma_and_line_number(tmp_path: Path) -> None:
    """CSV отдаёт одну запись за раз и не рвёт запятую внутри кавычек."""
    path = tmp_path / "events.csv"
    path.write_text(
        "timestamp,level,source,message\n"
        '2026-10-07T12:00:00+03:00,INFO,"книги, чтение",Привет\n',
        encoding="utf-8",
    )
    rows = list(iter_csv_records(path))
    assert len(rows) == 1
    line_number, record = rows[0]
    assert line_number == 2
    assert record["source"] == "книги, чтение"
    assert record["message"] == "Привет"


def test_csv_line_number_follows_multiline_field(tmp_path: Path) -> None:
    """Номер строки CSV — последняя физическая строка записи."""
    path = tmp_path / "multi.csv"
    path.write_text(
        "timestamp,level,source,message\n"
        '2026-10-07T12:00:00+03:00,INFO,loader,"hello\n'
        'world"\n',
        encoding="utf-8",
    )
    rows = list(iter_csv_records(path))
    assert len(rows) == 1
    line_number, record = rows[0]
    assert line_number == 3
    assert record["message"] == "hello\nworld"


def test_jsonl_parser_reads_objects_and_skips_blank_line(tmp_path: Path) -> None:
    """JSONL отдаёт объекты по строкам, пустая строка не является событием."""
    path = tmp_path / "events.jsonl"
    path.write_text(
        '\n{"name": "Анна", "visits": 3}\n',
        encoding="utf-8",
    )
    lines = list(iter_jsonl_lines(path))
    assert lines[0] == (1, "\n")
    assert parse_jsonl_line(lines[0][1]) is None
    record = parse_jsonl_line(lines[1][1])
    assert record is not None
    assert record["name"] == "Анна"
    assert record["visits"] == 3
    assert lines[1][0] == 2


def test_jsonl_parser_rejects_broken_line_and_non_object() -> None:
    """Плохой JSON и не-объект являются ошибкой события."""
    with pytest.raises(InvalidEventError, match="JSON"):
        parse_jsonl_line("not-json\n")
    with pytest.raises(InvalidEventError, match="JSON-объект"):
        parse_jsonl_line("[1, 2]\n")


def test_empty_files_have_no_records(tmp_path: Path) -> None:
    """Пустой файл не содержит ни одной записи."""
    csv_path = tmp_path / "empty.csv"
    jsonl_path = tmp_path / "empty.jsonl"
    csv_path.write_text("", encoding="utf-8")
    jsonl_path.write_text("", encoding="utf-8")
    assert list(iter_csv_records(csv_path)) == []
    assert list(iter_jsonl_lines(jsonl_path)) == []


def test_package_reads_logs_line_by_line() -> None:
    """В пакете нет чтения всего файла через read() или readlines()."""
    src = Path(__file__).resolve().parents[1] / "src"
    for path in src.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "readlines" not in text
        assert ".read(" not in text
