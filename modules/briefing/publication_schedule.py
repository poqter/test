"""The regular briefing calendar is independent of market holidays."""
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

KST = ZoneInfo('Asia/Seoul')
PUBLICATION_TIME = time(8)


def is_regular_day(day):
    return day.weekday() < 5


def previous_regular_day(day):
    previous = day - timedelta(days=1)
    while not is_regular_day(previous):
        previous -= timedelta(days=1)
    return previous


def monday_window_start(as_of):
    local = as_of.astimezone(KST)
    if local.weekday() == 0:
        return datetime.combine(previous_regular_day(local.date()), PUBLICATION_TIME, KST)
    return None
