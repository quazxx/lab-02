"""Интеграционные тесты CLI во временном каталоге."""

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"


def run_cli(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    """Запускает python -m streamstats и возвращает результат."""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(SRC)
    return subprocess.run(
        [sys.executable, "-m", "streamstats", *args],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


def test_help_lists_analyze_command() -> None:
    """python -m streamstats --help завершается нулём и показывает analyze."""
    result = run_cli(["--help"], ROOT)
    assert result.returncode == 0
    assert "analyze" in result.stdout
    assert "streamstats" in result.stdout


def test_cli_merges_files_and_writes_log(tmp_path: Path) -> None:
    """CLI пишет JSON и лог во временный каталог."""
    first = tmp_path / "a.csv"
    second = tmp_path / "b.csv"
    output = tmp_path / "report.json"
    log_path = tmp_path / "run.log"
    first.write_text(
        "timestamp,level,source,message\n"
        "2026-10-07T12:00:00+03:00,INFO,загрузчик,Начало чтения\n",
        encoding="utf-8",
    )
    second.write_text(
        "timestamp,level,source,message\n2026-10-07T08:00:00Z,ERROR,api,Сбой\n",
        encoding="utf-8",
    )
    result = run_cli(
        [
            "analyze",
            str(first),
            str(second),
            "--format",
            "csv",
            "--output",
            str(output),
            "--log",
            str(log_path),
        ],
        tmp_path,
    )
    assert result.returncode == 0
    assert output.is_file()
    assert log_path.is_file()
    assert "Начало чтения" in log_path.read_text(encoding="utf-8")
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["total_events"] == 2
    assert payload["by_source"]["загрузчик"] == 1
    assert payload["first_timestamp"] == "2026-10-07T08:00:00Z"
    assert "загрузчик" in output.read_text(encoding="utf-8")


def test_cli_bad_row_exits_with_code_2(tmp_path: Path) -> None:
    """Повреждённая строка дает код 2."""
    source = tmp_path / "bad.jsonl"
    output = tmp_path / "report.json"
    log_path = tmp_path / "run.log"
    source.write_text(
        '{"timestamp":"2026-10-07T12:00:00+00:00","level":"INFO",'
        '"source":"api","message":"ok"}\n'
        "not-json\n",
        encoding="utf-8",
    )
    result = run_cli(
        [
            "analyze",
            str(source),
            "--format",
            "jsonl",
            "--output",
            str(output),
            "--log",
            str(log_path),
        ],
        tmp_path,
    )
    assert result.returncode == 2
    assert "bad.jsonl" in result.stderr
    assert ":2:" in result.stderr
    assert not output.exists()
    assert "ERROR" in log_path.read_text(encoding="utf-8")


def test_cli_skip_invalid_exits_with_code_0(tmp_path: Path) -> None:
    """--skip-invalid дает код 0."""
    source = tmp_path / "bad.jsonl"
    output = tmp_path / "report.json"
    log_path = tmp_path / "run.log"
    source.write_text(
        '{"timestamp":"2026-10-07T12:00:00+00:00","level":"INFO",'
        '"source":"api","message":"ok"}\n'
        "not-json\n"
        '{"timestamp":"2026-10-07T13:00:00+00:00","level":"ERROR",'
        '"source":"api","message":"after"}\n',
        encoding="utf-8",
    )
    result = run_cli(
        [
            "analyze",
            source.name,
            "--format",
            "jsonl",
            "--output",
            output.name,
            "--skip-invalid",
            "--log",
            log_path.name,
        ],
        tmp_path,
    )
    assert result.returncode == 0
    assert "WARNING" in result.stderr
    assert "bad.jsonl" in result.stderr
    log_text = log_path.read_text(encoding="utf-8")
    assert "WARNING" in log_text
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["skipped_invalid"] == 1
    assert payload["total_events"] == 2
    assert payload["by_level"]["ERROR"] == 1
