"""Ошибки пакета streamstats."""


class StreamStatsError(Exception):
    """Базовая ошибка анализа журнала."""


class UnsupportedFormatError(StreamStatsError):
    """Формат не csv и не jsonl."""


class InvalidEventError(StreamStatsError):
    """Запись не является корректным событием."""


class MissingFieldError(InvalidEventError):
    """Обязательного поля нет в записи."""


class EmptyValueError(InvalidEventError):
    """Поле есть, но значение пустое."""


class InvalidTimestampError(StreamStatsError):
    """Время не разбирается или записано без часового пояса."""


class CliConfigError(StreamStatsError):
    """Неверные параметры командной строки."""
