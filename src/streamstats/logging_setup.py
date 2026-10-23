"""Настройка записи лога в файл и в консоль."""

import logging
from pathlib import Path

from streamstats.constants import LOGGER_NAME
from streamstats.errors import StreamStatsError


def setup_logging(log_path: Path) -> logging.Logger:
    """Настраивает логгер."""
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
        handler.close()
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )
    try:
        file_handler = logging.FileHandler(
            log_path,
            mode="a",
            encoding="utf-8",
        )
    except OSError as error:
        raise StreamStatsError(f"не удалось открыть лог {log_path}: {error}") from error
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    logger.addHandler(console)
    return logger
