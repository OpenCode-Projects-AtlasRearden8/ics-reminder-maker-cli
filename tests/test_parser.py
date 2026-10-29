"""Tests for the reminders.txt parser."""

from __future__ import annotations

from datetime import date

import pytest

from ics_reminder_maker.parser import Reminder, RemindersError, parse_reminders

from helpers import read_fixture


def test_simple_fixture_parses_five_reminders():
    reminders = parse_reminders(read_fixture("reminders_simple.txt"))
    names = [r.name for r in reminders]
    assert names == [
        "License renewal",
        "Insurance window",
        "Car registration",
        "Furnace filter change",
        "Library books due",
    ]


def test_dates_and_recurrence_are_parsed():
    reminders = parse_reminders(read_fixture("reminders_simple.txt"))
    by_name = {r.name: r for r in reminders}

    license_renewal = by_name["License renewal"]
    assert license_renewal.start == date(2027, 1, 15)
    assert license_renewal.end is None
    assert license_renewal.recurrence == "yearly"
    assert license_renewal.note == "Bring checkbook and ID"

    insurance = by_name["Insurance window"]
    assert insurance.start == date(2026, 11, 1)
    assert insurance.end == date(2026, 11, 30)
    assert insurance.recurrence == "none"
    assert insurance.is_range

    car = by_name["Car registration"]
    assert car.lead_days == [30, 0]
    assert car.note == ""

    filter_change = by_name["Furnace filter change"]
    assert filter_change.recurrence == "monthly"
    assert filter_change.lead_days == [0]

    library = by_name["Library books due"]
    assert library.lead_days == [3, 0]


def test_kitchen_sink_fixture():
    reminders = parse_reminders(read_fixture("reminders_kitchen_sink.txt"))
    assert len(reminders) == 5
    by_name = {r.name: r for r in reminders}
    assert by_name['Passport, visas & "papers"'].lead_days == [180]
    assert by_name["Painting window"].is_range
    assert by_name["Pet vaccine booster"].recurrence == "yearly"
    assert by_name["Smoke detector batteries"].note == ""


def test_lead_days_are_sorted_and_deduplicated_across_lines():
    reminders = parse_reminders("A | 2026-11-15 | 7,3,7,0")
    assert reminders[0].lead_days == [7, 3, 0]


def test_last_day_property():
    single = parse_reminders("A | 2026-11-15")[0]
    assert single.last_day == date(2026, 11, 15)
    window = parse_reminders("B | 2026-11-01..2026-11-30")[0]
    assert window.last_day == date(2026, 11, 30)


def test_blank_and_comment_lines_are_ignored():
    reminders = parse_reminders("# comment\n\n   \nA | 2026-11-15\n# another\n")
    assert [r.name for r in reminders] == ["A"]


def test_case_insensitive_recurrence():
    reminders = parse_reminders("A | 2026-11-15 | | YEARLY ")
    assert reminders[0].recurrence == "yearly"


def test_line_numbers_are_kept():
    reminders = parse_reminders("A | 2026-11-15\n# comment\nB | 2026-11-16\n")
    assert reminders[0].lineno == 1
    assert reminders[1].lineno == 3


def test_errors_report_every_bad_line_at_once():
    fixture = read_fixture("reminders_errors.txt")
    with pytest.raises(RemindersError) as excinfo:
        parse_reminders(fixture)
    message = str(excinfo.value)
    # all of these problems are in the fixture
    assert "line 2" in message
    assert "line 3" in message
    assert "line 4" in message
    assert "line 5" in message
    assert "line 6" in message
    assert "line 7" in message
    assert "line 8" in message
    # the good line produced a reminder before the raise
    assert "line 1" not in message


def test_error_mentions_bad_recurrence_value():
    with pytest.raises(RemindersError) as excinfo:
        parse_reminders("A | 2026-12-01 | 7 | weekly | note here")
    assert "weekly" in str(excinfo.value)


def test_four_fields_with_free_text_means_note_not_recurrence():
    reminders = parse_reminders("A | 2026-11-15 | 7 | Compare quotes early")
    assert reminders[0].recurrence == "none"
    assert reminders[0].note == "Compare quotes early"


def test_error_for_empty_name():
    with pytest.raises(RemindersError):
        parse_reminders("   | 2026-12-01")


def test_error_for_too_many_fields():
    with pytest.raises(RemindersError):
        parse_reminders("A | 2026-11-15 | 7 | yearly | note | extra | extra2")


def test_error_for_empty_lead_token():
    with pytest.raises(RemindersError):
        parse_reminders("A | 2026-11-15 | 7,")


def test_error_for_non_leap_feb_29():
    with pytest.raises(RemindersError):
        parse_reminders("A | 2027-02-29")


def test_reminder_dataclass_defaults():
    r = Reminder(name="X", start=date(2026, 1, 1))
    assert r.end is None
    assert r.lead_days == []
    assert r.note == ""
    assert r.recurrence == "none"
    assert r.last_day == r.start
