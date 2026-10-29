"""Command-line interface for ics-reminder-maker."""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from ics_reminder_maker import __version__
from ics_reminder_maker.icsgen import (
    CalendarError,
    build_calendar_text,
    build_mega_event,
    build_mega_text,
)
from ics_reminder_maker.parser import RemindersError, parse_reminders

EPILOG = """\
example reminders.txt:
  License renewal | 2027-01-15 | 30,7,0 | yearly | Bring checkbook
  Insurance window | 2026-11-01..2026-11-30 | 14,7 | Compare quotes early
  Car registration | 2026-12-01 | 30,0
  Furnace filter | 2027-03-01 | 0 | monthly | Check size MERV 11
"""


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ics-reminder-maker",
        description=(
            "Turn a plain reminders.txt file into RFC 5545 calendar (.ics) files "
            "with all-day events and lead-time alerts. Works fully offline."
        ),
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "input",
        type=Path,
        help="path to your reminders.txt file",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        metavar="PATH",
        help=(
            "output .ics file or directory (default: <input stem>.ics in the "
            "current directory)"
        ),
    )
    parser.add_argument(
        "--mega",
        action="store_true",
        help=(
            "also write a once-a-year whole-home-admin-day .ics file next to "
            "the main output"
        ),
    )
    parser.add_argument(
        "--admin-month",
        type=int,
        choices=range(1, 13),
        default=None,
        metavar="1-12",
        help="month for the yearly Whole-Home Admin Day (default: month of the earliest reminder)",
    )
    parser.add_argument(
        "--admin-day",
        type=int,
        choices=range(1, 32),
        default=None,
        metavar="1-31",
        help="day of month for the yearly Whole-Home Admin Day (default: day of the earliest reminder)",
    )
    parser.add_argument(
        "--year",
        type=int,
        default=None,
        metavar="YYYY",
        help="only include reminders whose first date falls in this year (no effect on yearly/monthly repeating ones)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="show what would be written without creating any files",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="only print errors",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    return parser


def _resolve_output_paths(output: Path | None, input_path: Path) -> Path:
    if output is None:
        main = Path.cwd() / f"{input_path.stem}.ics"
        return main
    if output.suffix == ".ics" or output.is_file():
        return output
    return output / f"{input_path.stem}.ics"


_DAYS_IN_MONTH = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)


def _pin_day_in_year(year: int, month: int, day: int) -> tuple[int, bool]:
    """Return (usable day-of-month, whether the requested day was reduced)."""
    limit = _DAYS_IN_MONTH[month - 1]
    if month == 2:
        is_leap = (year % 4 == 0 and year % 100 != 0) or year % 400 == 0
        if is_leap:
            limit = 29
    if day > limit:
        return limit, True
    return day, False


def _admin_day_from_parts(month: int | None, day: int | None, earliest: date) -> tuple[date, list[str]]:
    """Combine requested month/day with the earliest reminder date.

    Uses the earliest reminder's year; if the resulting date is already in
    the past relative to the earliest reminder, it moves to the next year so
    the first occurrence is still upcoming. Impossible dates (Feb 31, etc.)
    slide back to the last real day of that month.
    """
    warnings: list[str] = []
    month = month if month is not None else earliest.month
    day = day if day is not None else earliest.day
    year = earliest.year
    picked, overflow = _pin_day_in_year(year, month, day)
    if overflow:
        warnings.append(
            f"note: there is no day {day} in month {month}; "
            f"using day {picked} instead"
        )
    admin_day = date(year, month, picked)
    if admin_day < earliest:
        picked, overflow = _pin_day_in_year(year + 1, month, day)
        if overflow:
            warnings.append(
                f"note: there is no day {day} in month {month}; "
                f"using day {picked} instead"
            )
        admin_day = date(year + 1, month, picked)
    unique_warnings = list(dict.fromkeys(warnings))
    return admin_day, unique_warnings


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    input_path: Path = args.input
    if not input_path.is_file():
        parser.error(f"reminders file not found: {input_path}")

    text = input_path.read_text(encoding="utf-8-sig")
    try:
        reminders = parse_reminders(text)
    except RemindersError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if args.year is not None:
        filtered = [
            r for r in reminders if r.start.year == args.year or r.recurrence != "none"
        ]
    else:
        filtered = list(reminders)

    if not filtered:
        print(
            "Error: no reminders to write (check --year filtering or the file contents).",
            file=sys.stderr,
        )
        return 1

    try:
        calendar_text = build_calendar_text(filtered)
    except CalendarError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    warnings: list[str] = []
    mega_path: Path | None = None
    mega_text: str | None = None
    admin_day: date | None = None
    if args.mega:
        earliest = min(r.start for r in filtered)
        admin_day, warnings = _admin_day_from_parts(
            args.admin_month, args.admin_day, earliest
        )
        mega = build_mega_event(filtered, admin_day=admin_day)
        mega_text = build_mega_text(mega)

    main_path = _resolve_output_paths(args.output, input_path)
    if args.mega:
        mega_path = main_path.with_name("whole-home-admin-day.ics")

    if args.dry_run:
        if not args.quiet:
            print(f"Would write: {main_path}")
            print(f"  - {len(filtered)} all-day event(s)")
            alarm_count = sum(len(r.lead_days) for r in filtered)
            print(f"  - {alarm_count} lead-time alert(s)")
            if mega_path and mega_text:
                print(f"Would write: {mega_path}")
                print(f"  - 1 yearly Whole-Home Admin Day on {admin_day.isoformat()}")
        for warning in warnings:
            print(warning, file=sys.stderr)
        return 0

    main_path.parent.mkdir(parents=True, exist_ok=True)
    with open(main_path, "wb") as handle:
        handle.write(calendar_text.encode("utf-8"))
    if mega_path and mega_text:
        mega_path.parent.mkdir(parents=True, exist_ok=True)
        with open(mega_path, "wb") as handle:
            handle.write(mega_text.encode("utf-8"))

    if not args.quiet:
        alarm_count = sum(len(r.lead_days) for r in filtered)
        print(f"Wrote {main_path} ({len(filtered)} event(s), {alarm_count} alert(s))")
        if mega_text:
            print(f"Wrote {mega_path} (yearly Whole-Home Admin Day on {admin_day.isoformat()})")
        if warnings:
            for warning in warnings:
                print(warning)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
