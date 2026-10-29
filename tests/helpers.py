"""Shared helpers for the test suite: an RFC 5545 mini-parser."""

from __future__ import annotations

import re
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"
CRLF = "\r\n"


def fixture_path(name: str) -> Path:
    return FIXTURES / name


def read_fixture(name: str) -> str:
    return fixture_path(name).read_text(encoding="utf-8")


def read_bytes_text(path) -> str:
    """Read a file as bytes and decode, preserving CRLF line endings."""
    return Path(path).read_bytes().decode("utf-8")


def unfold(text: str) -> list[str]:
    """Reverse RFC 5545 folding and return logical content lines."""
    no_fold = re.sub(r"\r\n[ \t]", "", text)
    logical = no_fold.split(CRLF)
    while logical and logical[-1] == "":
        logical.pop()
    return logical


def parse_calendar(text: str) -> dict:
    """Structurally validate a VCALENDAR and index its properties.

    Asserts the basic RFC 5545 shape and returns a dict with:
      version, prodid, calscale, method, events
    where each event is a dict of ``{property_name: value}`` (last occurrence
    wins for repeated names) plus ``alarms``: a list of {name: value} dicts.
    """
    assert "\r\n" in text, "calendar must use CRLF line endings"
    assert text.endswith(CRLF), "calendar must end with CRLF"
    lines = unfold(text)
    assert lines[0] == "BEGIN:VCALENDAR"
    assert lines[-1] == "END:VCALENDAR"
    # every physical line obeys the 75-octet rule
    for raw in text.split(CRLF)[:-1]:
        assert len(raw.encode("utf-8")) <= 75, f"line too long: {raw!r}"

    calendar: dict = {"events": []}
    event: dict | None = None
    alarm: dict | None = None
    depth_component = 0

    for line in lines:
        if line.startswith(("BEGIN:", "END:")):
            kind, _, value = line.partition(":")
            if kind == "BEGIN":
                depth_component += 1
            else:
                depth_component -= 1
                assert depth_component >= 0, f"unbalanced {line}"
            if value == "VEVENT" and kind == "BEGIN":
                assert event is None, "nested VEVENT"
                event = {"alarms": []}
            elif value == "VEVENT" and kind == "END":
                assert alarm is None, "unclosed VALARM inside VEVENT"
                if event is not None:
                    calendar["events"].append(event)
                    event = None
            elif value == "VALARM" and kind == "BEGIN":
                assert event is not None, "VALARM outside VEVENT"
                assert alarm is None, "nested VALARM"
                alarm = {}
            elif value == "VALARM" and kind == "END":
                assert alarm is not None
                event["alarms"].append(alarm)
                alarm = None
            continue
        if line == "":
            raise AssertionError("blank content line inside calendar")
        if ":" not in line:
            raise AssertionError(f"content line without colon: {line!r}")
        name, _, value = line.partition(":")
        if alarm is not None:
            alarm[name] = value
        elif event is not None:
            event[name] = value
        else:
            calendar[name] = value
    assert event is None, "unclosed VEVENT"
    assert alarm is None, "unclosed VALARM"
    assert depth_component == 0, "unbalanced BEGIN/END pairs"
    return calendar


def prop(line_name: str, event: dict) -> str:
    """Convenience: return an event property value."""
    return event[line_name]


def split_line(line: str) -> tuple[str, dict, str]:
    """Split one unfolded content line into (name, params, value)."""
    head, _, value = line.partition(":")
    parts = head.split(";")
    params: dict[str, str] = {}
    for part in parts[1:]:
        key, _, val = part.partition("=")
        params[key] = val
    return parts[0], params, value
