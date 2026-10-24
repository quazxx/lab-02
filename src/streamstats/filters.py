"""Фильтры."""

from collections.abc import Iterator
from datetime import datetime

from streamstats.models import Event


def filter_events(
    events: Iterator[Event],
    level: str | None = None,
    source: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
) -> Iterator[Event]:
    """Отдаёт события, которые прошли условия."""
    for event in events:
        if level is not None and event.level != level:
            continue
        if source is not None and event.source != source:
            continue
        if since is not None and event.timestamp < since:
            continue
        if until is not None and event.timestamp > until:
            continue
        yield event
