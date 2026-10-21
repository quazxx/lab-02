"""Модель одного события журнала."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Event:
    """Событие после проверки полей.

    timestamp - момент времени для сравнения.
    timestamp_text - исходная строка, её пишем в отчёт.
    """

    timestamp: datetime
    timestamp_text: str
    level: str
    source: str
    message: str
