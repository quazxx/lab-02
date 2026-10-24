"""Тесты JSON-отчёта."""

import json
from pathlib import Path

from streamstats.analysis import collect_stats
from streamstats.report import build_report, write_json_report

SAMPLE = (
    "timestamp,level,source,message\n"
    "2026-10-07T12:00:00+03:00,INFO,загрузчик,Начало чтения\n"
    "2026-10-07T09:30:00+00:00,ERROR,api,Сбой запроса\n"
    "2026-10-07T10:00:00+00:00,DEBUG,worker,Пауза\n"
)


def test_same_input_gives_byte_identical_json(tmp_path: Path) -> None:
    """Два прогона одного файла дают один и тот же JSON, кириллица читаема."""
    source = tmp_path / "events.csv"
    source.write_text(SAMPLE, encoding="utf-8")
    first = tmp_path / "a.json"
    second = tmp_path / "b.json"
    left = build_report(collect_stats([source], "csv", skip_invalid=False))
    right = build_report(collect_stats([source], "csv", skip_invalid=False))
    write_json_report(left, first)
    write_json_report(right, second)
    assert first.read_bytes() == second.read_bytes()
    text = first.read_text(encoding="utf-8")
    assert text.startswith('{\n  "total_events"')
    assert "загрузчик" in text
    assert "\\u" not in text
    payload = json.loads(text)
    assert payload["by_level"]["DEBUG"] == 1
    assert payload["by_source"]["api"] == 1
    assert payload["top_error_sources"] == [{"source": "api", "count": 1}]
    assert payload["first_timestamp"] == "2026-10-07T12:00:00+03:00"
    assert payload["skipped_invalid"] == 0
