"""Потоковое чтение CSV и JSONL."""

import csv
import json
from collections.abc import Iterator
from pathlib import Path

from streamstats.errors import InvalidEventError


def iter_csv_records(path: Path) -> Iterator[tuple[int, dict[str, object]]]:
    """Отдаёт строки CSV по одной: номер строки и словарь полей.

    Номер - последняя физическая строка записи. Заголовок в счёт событий не входит.
    """
    with path.open(encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        for row in reader:
            record: dict[str, object] = {}
            for key, value in row.items():
                if key is None:
                    continue
                record[key] = value
            yield reader.line_num, record


def iter_jsonl_lines(path: Path) -> Iterator[tuple[int, str]]:
    """Отдаёт физические строки JSONL вместе с номером в файле."""
    with path.open(encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            yield line_number, line


def parse_jsonl_line(line: str) -> dict[str, object] | None:
    """Разбирает одну строку JSONL.

    Пустая строка не считается событием, функция возвращает None.
    Текст не в формате JSON и значение не-объект - ошибка события.
    """
    if line.strip() == "":
        return None
    try:
        parsed = json.loads(line)
    except json.JSONDecodeError as error:
        raise InvalidEventError(f"строка не является JSON: {error.msg}") from error
    if not isinstance(parsed, dict):
        raise InvalidEventError("ожидался JSON-объект")
    record: dict[str, object] = {}
    for key, value in parsed.items():
        if not isinstance(key, str):
            raise InvalidEventError("ключ JSON должен быть строкой")
        record[key] = value
    return record
