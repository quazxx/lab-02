"""Командная строка."""

import argparse
import sys
from datetime import datetime
from pathlib import Path

from streamstats.analysis import collect_stats, get_logger, parse_timestamp
from streamstats.constants import (
    DEFAULT_LOG_NAME,
    EXIT_CODE_ERROR,
    LEVELS,
    SUPPORTED_FORMATS,
)
from streamstats.errors import CliConfigError, InvalidTimestampError, StreamStatsError
from streamstats.logging_setup import setup_logging
from streamstats.report import build_report, write_json_report


def build_parser() -> argparse.ArgumentParser:
    """Собирает разбор аргументов команды analyze."""
    parser = argparse.ArgumentParser(
        prog="streamstats",
        description=(
            "Потоковый анализ журналов CSV и JSONL. "
            "Команда: streamstats analyze INPUT "
            "--format csv|jsonl --output REPORT.json"
        ),
    )
    subparsers = parser.add_subparsers(dest="command")
    analyze = subparsers.add_parser(
        "analyze",
        help="Собрать статистику и записать отчёт",
    )
    analyze.add_argument(
        "inputs",
        nargs="+",
        type=Path,
        metavar="INPUT",
        help="Один или несколько файлов журнала",
    )
    analyze.add_argument(
        "--format",
        required=True,
        choices=SUPPORTED_FORMATS,
        help="Формат входных файлов: csv или jsonl",
    )
    analyze.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Куда записать JSON-отчёт",
    )
    analyze.add_argument(
        "--skip-invalid",
        action="store_true",
        help="Пропускать повреждённые строки вместо остановки",
    )
    analyze.add_argument(
        "--log",
        type=Path,
        default=Path(DEFAULT_LOG_NAME),
        help="Файл журнала работы программы",
    )
    analyze.add_argument(
        "--level",
        choices=LEVELS,
        help="Оставить только события этого уровня",
    )
    analyze.add_argument(
        "--source",
        help="Оставить только события этого источника",
    )
    analyze.add_argument(
        "--since",
        help="Оставить события не раньше этого времени ISO 8601",
    )
    analyze.add_argument(
        "--until",
        help="Оставить события не позже этого времени ISO 8601",
    )
    return parser


def _optional_timestamp(text: str | None, flag_name: str) -> datetime | None:
    """Разбирает необязательную границу времени из аргументов CLI."""
    if text is None:
        return None
    try:
        return parse_timestamp(text)
    except InvalidTimestampError as error:
        raise CliConfigError(f"{flag_name}: {error}") from error


def execute(args: argparse.Namespace) -> None:
    """Запускает анализ и записывает отчёт. При ошибке завершает процесс с кодом 2."""
    try:
        logger = setup_logging(Path(args.log))
        since = _optional_timestamp(args.since, "--since")
        until = _optional_timestamp(args.until, "--until")
        source: str | None = args.source
        if source == "":
            raise CliConfigError("параметр --source не может быть пустым")
        paths: list[Path] = []
        for item in args.inputs:
            paths.append(Path(item))
        level: str | None = args.level
        stats = collect_stats(
            paths,
            args.format,
            bool(args.skip_invalid),
            level=level,
            source=source,
            since=since,
            until=until,
        )
        report = build_report(stats)
        output = Path(args.output)
        write_json_report(report, output)
        logger.info(f"Отчёт записан: {output}")
        print(f"Отчёт записан: {output}")
    except StreamStatsError as error:
        get_logger().error(error)
        print(str(error), file=sys.stderr)
        raise SystemExit(EXIT_CODE_ERROR) from error
