"""ics-reminder-maker: turn a plain reminders.txt into RFC 5545 calendar files."""

from ics_reminder_maker.parser import Reminder, RemindersError, parse_reminders
from ics_reminder_maker.icsgen import CalendarError, build_calendar_text, build_mega_event

__version__ = "1.0.0"

__all__ = [
    "Reminder",
    "RemindersError",
    "CalendarError",
    "parse_reminders",
    "build_calendar_text",
    "build_mega_event",
    "__version__",
]
