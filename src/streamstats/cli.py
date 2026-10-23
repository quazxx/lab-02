"""Командная строка."""

import argparse
import sys
from pathlib import Path

from streamstats.analysis import collect_stats, get_logger
from streamstats.constants import DEFAULT_LOG_NAME, EXIT_CODE_ERROR, SUPPORTED_FORMATS
from streamstats.errors import StreamStatsError
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
    return parser


def execute(args: argparse.Namespace) -> None:
    """Запускает анализ и записывает отчёт. При ошибке завершает процесс с кодом 2."""
    try:
        logger = setup_logging(Path(args.log))
        paths: list[Path] = []
        for item in args.inputs:
            paths.append(Path(item))
        stats = collect_stats(paths, args.format, bool(args.skip_invalid))
        report = build_report(stats)
        output = Path(args.output)
        write_json_report(report, output)
        logger.info(f"Отчёт записан: {output}")
        print(f"Отчёт записан: {output}")
    except StreamStatsError as error:
        get_logger().error(error)
        print(str(error), file=sys.stderr)
        raise SystemExit(EXIT_CODE_ERROR) from error
