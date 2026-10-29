"""Generate RFC 5545 compliant iCalendar text from parsed reminders.

The output follows RFC 5545 (iCalendar 2.0):
- CRLF line endings
- lines longer than 75 octets folded per RFC 5545 section 3.1
- TEXT values escaped per section 3.3.11
- all-day events use DATE values (``DTSTART;VALUE=DATE``)
- multi-day windows use an exclusive ``DTEND;VALUE=DATE`` (the day after)
- lead-time alerts use ``TRIGGER;VALUE=DURATION`` alarms
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from ics_reminder_maker.parser import Reminder

PRODID = "-//Asdale Dynamics, LLC//ics-reminder-maker 1.0//EN"
CRLF = "\r\n"
MAX_LINE_OCTETS = 75


class CalendarError(ValueError):
    """Raised when a calendar cannot be generated from the given input."""


def _escape_text(value: str) -> str:
    escaped = value.replace("\\", "\\\\")
    escaped = escaped.replace(";", "\\;")
    escaped = escaped.replace(",", "\\,")
    escaped = escaped.replace("\r\n", "\\n").replace("\n", "\\n").replace("\r", "\\n")
    return escaped


def _fold(line: str) -> list[str]:
    """Fold a content line so no physical line exceeds 75 octets.

    Continuation lines start with a single space; that space counts toward
    the 75-octet limit, so it consumes one octet of the budget.
    """
    data = line.encode("utf-8")
    if len(data) <= MAX_LINE_OCTETS:
        return [line]
    chunks: list[bytes] = []
    start = 0
    limit = MAX_LINE_OCTETS
    while start < len(data):
        end = min(start + limit, len(data))
        if end < len(data):
            while end > start and (data[end] & 0xC0) == 0x80:
                end -= 1
        chunks.append(data[start:end])
        start = end
        limit = MAX_LINE_OCTETS - 1
    return [chunks[0].decode("utf-8")] + [
        " " + chunk.decode("utf-8") for chunk in chunks[1:]
    ]


def _uid(*parts: object) -> str:
    digest = hashlib.sha1("|".join(str(part) for part in parts).encode("utf-8"))
    return f"{digest.hexdigest()[:32]}@ics-reminder-maker.local"


def _dstamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _date_value(day: date) -> str:
    return day.strftime("%Y%m%d")


def _trigger(days_before: int) -> str:
    if days_before == 0:
        return "PT0S"
    return f"-P{days_before}D"


def _content_line(name: str, value: str) -> str:
    return CRLF.join(_fold(f"{name}:{value}"))


def _event_lines(reminder: Reminder) -> list[str]:
    lines = ["BEGIN:VEVENT"]
    lines.append(_content_line("UID", _uid(reminder.name, reminder.start, reminder.raw)))
    lines.append(_content_line("DTSTAMP", _dstamp()))
    lines.append(_content_line("DTSTART;VALUE=DATE", _date_value(reminder.start)))
    if reminder.is_range:
        lines.append(
            _content_line("DTEND;VALUE=DATE", _date_value(reminder.end + timedelta(days=1)))
        )
    if reminder.recurrence == "yearly":
        lines.append(_content_line("RRULE", "FREQ=YEARLY"))
    elif reminder.recurrence == "monthly":
        lines.append(_content_line("RRULE", "FREQ=MONTHLY"))

    description_parts = []
    if reminder.note:
        description_parts.append(reminder.note)
    if reminder.lead_days:
        shown_start = reminder.start.isoformat()
        if reminder.is_range:
            shown_start = f"{reminder.start.isoformat()} to {reminder.end.isoformat()}"
        description_parts.append(
            "Lead-time alerts planned " + ", ".join(str(d) for d in reminder.lead_days)
            + " day(s) before start."
        )
        description_parts.append(f"Scheduled window: {shown_start}")
    lines.append(_content_line("SUMMARY", reminder.name))
    lines.append(_content_line("DESCRIPTION", _escape_text("\n".join(description_parts))))
    lines.append(_content_line("TRANSP", "TRANSPARENT"))

    for days_before in reminder.lead_days:
        lines.append("BEGIN:VALARM")
        lines.append(_content_line("ACTION", "DISPLAY"))
        lines.append(
            _content_line(
                "DESCRIPTION",
                _escape_text(f"Reminder: {reminder.name} ({days_before} day(s) notice)"),
            )
        )
        lines.append(_content_line("TRIGGER;VALUE=DURATION", _trigger(days_before)))
        lines.append("END:VALARM")

    lines.append("END:VEVENT")
    return lines


def _calendar_lines(events: list[list[str]]) -> list[str]:
    lines = ["BEGIN:VCALENDAR"]
    lines.append(_content_line("VERSION", "2.0"))
    lines.append(_content_line("PRODID", PRODID))
    lines.append(_content_line("CALSCALE", "GREGORIAN"))
    lines.append(_content_line("METHOD", "PUBLISH"))
    for event in events:
        lines.extend(event)
    lines.append("END:VCALENDAR")
    return lines


def build_calendar_text(reminders: list[Reminder]) -> str:
    """Build the full .ics text for a list of reminders."""
    if not reminders:
        raise CalendarError("No reminders were provided, so there is nothing to write.")
    lines = _calendar_lines([_event_lines(reminder) for reminder in reminders])
    return CRLF.join(lines) + CRLF


def _mega_description(reminders: list[Reminder]) -> str:
    ordered = sorted(reminders, key=lambda r: (r.start, r.name))
    rows = [f"- {r.name} (starts {r.start.isoformat()})" for r in ordered]
    parts = ["Before you start: work through this checklist at home.",
             "Annual home-admin checklist:", *rows,
             "Made with ics-reminder-maker by Asdale Dynamics, LLC."]
    return "\n".join(parts)


@dataclass
class MegaEvent:
    """Everything needed for the once-a-year whole-home admin day."""

    summary: str
    occurrence: date
    description: str


def build_mega_event(reminders: list[Reminder], admin_day: date | None = None) -> MegaEvent:
    """Choose the admin day and description for the yearly mega event.

    The admin day defaults to the earliest reminder date in the file so that
    the output is sensible without inventing an arbitrary default.
    """
    if not reminders:
        raise CalendarError("No reminders were provided, so there is nothing to write.")
    if admin_day is None:
        admin_day = min(day.start for day in reminders)
    return MegaEvent(
        summary="Whole-Home Admin Day",
        occurrence=admin_day,
        description=_mega_description(reminders),
    )


def event_lines_for_mega(mega: MegaEvent) -> list[str]:
    lines = ["BEGIN:VEVENT"]
    lines.append(
        _content_line("UID", _uid(mega.summary, mega.occurrence, "whole-home-admin-day"))
    )
    lines.append(_content_line("DTSTAMP", _dstamp()))
    lines.append(_content_line("DTSTART;VALUE=DATE", _date_value(mega.occurrence)))
    lines.append(_content_line("DTEND;VALUE=DATE", _date_value(mega.occurrence + timedelta(days=1))))
    lines.append(_content_line("RRULE", "FREQ=YEARLY"))
    lines.append(_content_line("SUMMARY", mega.summary))
    lines.append(_content_line("DESCRIPTION", _escape_text(mega.description)))
    lines.append(_content_line("TRANSP", "TRANSPARENT"))
    lines.append("END:VEVENT")
    return lines


def build_mega_text(mega: MegaEvent) -> str:
    """Build the full .ics text for the yearly whole-home admin day."""
    lines = _calendar_lines([event_lines_for_mega(mega)])
    return CRLF.join(lines) + CRLF
