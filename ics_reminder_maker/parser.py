"""Parse a plain-text reminders file into Reminder objects.

File format (one reminder per line, fields separated by ``|``):

    Name | date | lead days | recurrence | note

Only the first two fields are required. ``date`` is ``YYYY-MM-DD`` for a
single-day event, or ``YYYY-MM-DD..YYYY-MM-DD`` for a multi-day window.

``lead days`` is a comma-separated list of whole numbers of days before the
event start when a reminder alarm should fire (``0`` = on the day, e.g.
``30,7,0``).

``recurrence`` is optional: ``yearly``, ``monthly``, or ``none`` (default).

``note`` is any free text. Lines starting with ``#`` are comments.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}$")
RECURRENCES = ("none", "yearly", "monthly")


class RemindersError(ValueError):
    """Raised when one or more reminder lines cannot be parsed."""

    def __init__(self, errors: list[str]):
        message = (
            "Could not parse reminders file.\n"
            + "\n".join(f"  - {error}" for error in errors)
        )
        super().__init__(message)
        self.errors = errors


@dataclass
class Reminder:
    """One reminder parsed from the reminders file."""

    name: str
    start: date
    end: date | None = None
    lead_days: list[int] = field(default_factory=list)
    note: str = ""
    recurrence: str = "none"
    lineno: int = 0
    raw: str = ""

    @property
    def last_day(self) -> date:
        return self.end if self.end is not None else self.start

    @property
    def is_range(self) -> bool:
        return self.end is not None


def parse_lead_days(text: str, lineno: int) -> list[int]:
    value = text.strip()
    if not value:
        return []
    days: list[int] = []
    seen: set[int] = set()
    for token in value.split(","):
        token = token.strip()
        if not token:
            raise RemindersError([f"line {lineno}: empty lead-time day in '{value}'"])
        try:
            number = int(token)
        except ValueError as exc:
            raise RemindersError(
                [f"line {lineno}: lead-time day '{token}' is not a whole number"]
            ) from exc
        if number < 0:
            raise RemindersError(
                [f"line {lineno}: lead-time day '{number}' must be 0 or more days"]
            )
        if number not in seen:
            days.append(number)
            seen.add(number)
    return sorted(days, reverse=True)


def parse_date_field(text: str, lineno: int) -> tuple[date, date | None]:
    value = text.strip()
    if not value:
        raise RemindersError([f"line {lineno}: the date field is empty"])
    if ".." in value:
        start_text, sep, end_text = value.partition("..")
        if not sep:
            raise RemindersError(
                [f"line {lineno}: date range '{value}' must use '..' between two dates"]
            )
        start = _one_date(start_text, lineno, value)
        end = _one_date(end_text, lineno, value)
        if end < start:
            raise RemindersError(
                [f"line {lineno}: date range '{value}' ends before it starts"]
            )
        return start, end
    return _one_date(value, lineno, value), None


def _one_date(text: str, lineno: int, whole: str) -> date:
    value = text.strip()
    if not DATE_RE.match(value):
        raise RemindersError(
            [
                f"line {lineno}: '{whole}' is not a valid date or range; "
                "dates must look like YYYY-MM-DD and ranges like YYYY-MM-DD..YYYY-MM-DD"
            ]
        )
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise RemindersError([f"line {lineno}: '{value}' is not a real calendar date"]) from exc


def _parse_line(line: str, lineno: int) -> Reminder:
    fields = line.split("|")
    if len(fields) not in (2, 3, 4, 5):
        raise RemindersError(
            [f"line {lineno}: expected 'name | date' plus optional fields, separated by '|'"]
        )
    name = fields[0].strip()
    if not name:
        raise RemindersError([f"line {lineno}: the reminder name is empty"])

    try:
        start, end = parse_date_field(fields[1], lineno)
        lead_days = parse_lead_days(fields[2], lineno) if len(fields) >= 3 else []
    except RemindersError:
        raise

    recurrence = "none"
    note = ""
    if len(fields) == 4:
        fourth = fields[3].strip()
        lower = fourth.lower()
        if fourth and lower in RECURRENCES:
            recurrence = lower
        else:
            # forgiving: treat anything else in this slot as the note
            note = fourth
    elif len(fields) == 5:
        fourth = fields[3].strip().lower()
        if fourth not in RECURRENCES:
            raise RemindersError(
                [
                    f"line {lineno}: recurrence '{fields[3].strip()}' is unknown; "
                    "use yearly, monthly, or none"
                ]
            )
        recurrence = fourth
        note = fields[4].strip()

    return Reminder(
        name=name,
        start=start,
        end=end,
        lead_days=lead_days,
        note=note,
        recurrence=recurrence,
        lineno=lineno,
        raw=line,
    )


def parse_reminders(text: str) -> list[Reminder]:
    """Parse the full text of a reminders file.

    Collects every problem before raising, so beginners see all broken lines
    at once instead of fixing them one at a time.
    """
    errors: list[str] = []
    reminders: list[Reminder] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        try:
            reminders.append(_parse_line(stripped, lineno))
        except RemindersError as exc:
            errors.extend(exc.errors)
    if errors:
        raise RemindersError(errors)
    return reminders
