"""Recognize a clock prefix only for newly created, untimed calendar events."""
import re

_PREFIX = re.compile(r"^([01]?[0-9]|2[0-3]):([0-5][0-9])[ \t]+([^ \t~～∼–—-].*)$")


_KOREAN = re.compile(r"^(?:(오전|오후)[ \t]*)?([0-9]{1,2})시(?:[ \t]*(반|[0-9]{1,2}분))?[ \t]+(.+)$")
_QUALIFIER = re.compile(r"^(?:까지|부터|쯤|경(?:에|\s|$)|정도|반(?:쯤|까지|부터|경|\s|$)|[0-9]+분|[~～∼–—-])")


def apply_title_clock(body):
    if body["kind"] == "휴무" or not body["time_pending"] or body["start_time"] or body["end_time"]:
        return
    match = _PREFIX.fullmatch(body["title"])
    if match:
        hour, minute, title = match.groups()
    else:
        match = _KOREAN.fullmatch(body["title"])
        if not match:
            return
        period, hour, minutes, title = match.groups()
        hour = int(hour)
        minute = 30 if minutes == "반" else int(minutes[:-1]) if minutes else 0
        if minute > 59 or hour > 23 or (period and not 1 <= hour <= 12):
            return
        if period:
            hour = hour % 12 + (12 if period == "오후" else 0)
    title = title.strip()
    if title and not _QUALIFIER.match(title):
        body.update(title=title, start_time=f"{int(hour):02}:{int(minute):02}:00", time_pending=False)
