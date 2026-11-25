"""Recognize a clock prefix only for newly created, untimed calendar events."""
import re

_PREFIX = re.compile(r"^([01]?[0-9]|2[0-3]):([0-5][0-9])[ \t]+([^ \t~～∼–—-].*)$")


def apply_title_clock(body):
    if body["kind"] == "휴무" or not body["time_pending"] or body["start_time"] or body["end_time"]:
        return
    match = _PREFIX.fullmatch(body["title"])
    if match:
        hour, minute, title = match.groups()
        body.update(title=title, start_time=f"{int(hour):02}:{minute}:00", time_pending=False)
