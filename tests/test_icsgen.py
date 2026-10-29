"""Tests for ICS generation against RFC 5545 expectations."""

from __future__ import annotations

import re
from datetime import date

import pytest

from ics_reminder_maker.icsgen import (
    build_calendar_text,
    build_mega_event,
    build_mega_text,
)
from ics_reminder_maker.parser import parse_reminders

from helpers import parse_calendar, read_fixture, unfold


@pytest.fixture
def simple_text():
    return build_calendar_text(parse_reminders(read_fixture("reminders_simple.txt")))


@pytest.fixture
def kitchen_text():
    return build_calendar_text(parse_reminders(read_fixture("reminders_kitchen_sink.txt")))


@pytest.fixture
def simple_events(simple_text):
    return parse_calendar(simple_text)


def test_calendar_header(simple_events):
    assert simple_events["VERSION"] == "2.0"
    assert "PRODID" in simple_events
    assert simple_events.get("CALSCALE") == "GREGORIAN"
    assert simple_events.get("METHOD") == "PUBLISH"
    assert len(simple_events["events"]) == 5


def test_all_day_dtstart(simple_events):
    events = simple_events["events"]
    by_name = {ev["SUMMARY"]: ev for ev in events}
    renewal = by_name["License renewal"]
    # the mini-parser keys date properties with their params attached
    assert renewal["DTSTART;VALUE=DATE"] == "20270115"
    # a single-day event has no DTEND
    assert "DTEND;VALUE=DATE" not in renewal


def test_range_uses_exclusive_dtend():
    text = build_calendar_text(parse_reminders("W | 2026-11-01..2026-11-30 | 7"))
    cal = parse_calendar(text)
    event = cal["events"][0]
    assert event["DTSTART;VALUE=DATE"] == "20261101"
    assert event["DTEND;VALUE=DATE"] == "20261201"


def test_rrule_for_recurring(simple_events):
    by_name = {ev["SUMMARY"]: ev for ev in simple_events["events"]}
    assert by_name["License renewal"]["RRULE"] == "FREQ=YEARLY"
    assert by_name["Furnace filter change"]["RRULE"] == "FREQ=MONTHLY"
    assert "RRULE" not in by_name["Library books due"]


def test_lead_time_alarms(simple_events):
    by_name = {ev["SUMMARY"]: ev for ev in simple_events["events"]}
    renewal = by_name["License renewal"]
    assert len(renewal["alarms"]) == 3
    triggers = {a["TRIGGER;VALUE=DURATION"] for a in renewal["alarms"]}
    assert triggers == {"-P30D", "-P7D", "PT0S"}
    descriptions = {a["DESCRIPTION"] for a in renewal["alarms"]}
    assert any("30 day(s) notice" in d for d in descriptions)
    assert all(a["ACTION"] == "DISPLAY" for a in renewal["alarms"])


def test_zero_lead_day_is_pt0s_not_pd0():
    text = build_calendar_text(parse_reminders("A | 2026-11-20 | 0"))
    cal = parse_calendar(text)
    assert cal["events"][0]["alarms"][0]["TRIGGER;VALUE=DURATION"] == "PT0S"


def test_duplicate_lead_days_are_skipped():
    text = build_calendar_text(parse_reminders(read_fixture("reminders_dup_alerts.txt")))
    cal = parse_calendar(text)
    triggers = [a["TRIGGER;VALUE=DURATION"] for a in cal["events"][0]["alarms"]]
    assert triggers == ["-P7D", "-P3D", "PT0S"]


def test_text_escaping(kitchen_text):
    lines = unfold(kitchen_text)
    joined = "\n".join(lines)
    # commas/semicolons/backslashes escaped in TEXT values
    assert "Budget\\, bid\\; check references" in joined
    assert "Passport\\, visas & \"papers\"" in joined
    assert "\\,comma" in joined


def test_line_folding_and_unfolding_round_trips(kitchen_text):
    unfolded = unfold(kitchen_text)
    summary_lines = [l for l in unfolded if l.startswith("SUMMARY:")]
    long_summary = [l for l in summary_lines if "Househould deep clean" in l]
    assert long_summary, "folding kept the summary findable"
    # the original long description must unfold back to full text
    joined = "\n".join(unfolded)
    assert "force line folding" in joined
    assert "远远 exceed seventy five octets" in joined


def test_crlf_everywhere(kitchen_text):
    raw = kitchen_text.encode("utf-8")
    # no bare LF allowed
    assert raw.replace(b"\r\n", b"").count(b"\n") == 0


def test_uids_are_stable_and_unique():
    text_one = build_calendar_text(parse_reminders(read_fixture("reminders_simple.txt")))
    text_two = build_calendar_text(parse_reminders(read_fixture("reminders_simple.txt")))
    uids_one = re.findall(r"^UID:([^\r\n]+)", text_one, flags=re.M)
    uids_two = re.findall(r"^UID:([^\r\n]+)", text_two, flags=re.M)
    assert uids_one == uids_two
    # folded UID lines are unlikely; if one folds, unfold first (already done below)
    assert len(set(uids_one)) == len(uids_one)
    assert all(uid.endswith("@ics-reminder-maker.local") for uid in uids_one)


def test_dtstamp_format():
    text = build_calendar_text(parse_reminders("A | 2026-11-15"))
    dtstamp = re.search(r"^DTSTAMP:([^\r\n]+)\r?$", text, flags=re.M)
    assert dtstamp and re.fullmatch(r"\d{8}T\d{6}Z", dtstamp.group(1)), (
        "DTSTAMP must be UTC basic format"
    )


def test_transparent_events():
    text = build_calendar_text(parse_reminders("A | 2026-11-15"))
    assert "TRANSP:TRANSPARENT" in text


def test_empty_reminders_raise():
    with pytest.raises(Exception):
        build_calendar_text([])


def test_mega_event_defaults_and_description():
    reminders = parse_reminders(read_fixture("reminders_simple.txt"))
    mega = build_mega_event(reminders)
    assert mega.summary == "Whole-Home Admin Day"
    # default admin day is the earliest reminder date
    assert mega.occurrence == date(2026, 11, 1)
    rows = [line for line in mega.description.split("\n") if line.startswith("- ")]
    assert rows[0].startswith("- Insurance window")
    assert any("License renewal" in row for row in rows)


def test_mega_text_structure():
    reminders = parse_reminders(read_fixture("reminders_single.txt"))
    mega = build_mega_event(reminders, admin_day=date(2027, 3, 20))
    text = build_mega_text(mega)
    cal = parse_calendar(text)
    event = cal["events"][0]
    assert event["SUMMARY"] == "Whole-Home Admin Day"
    assert event["DTSTART;VALUE=DATE"] == "20270320"
    assert event["RRULE"] == "FREQ=YEARLY"


def test_mega_is_yearly_recurring_with_checklist():
    reminders = parse_reminders(read_fixture("reminders_simple.txt"))
    mega = build_mega_event(reminders, admin_day=date(2027, 3, 20))
    text = build_mega_text(mega)
    cal = parse_calendar(text)
    assert len(cal["events"]) == 1
    event = cal["events"][0]
    assert event["DTSTART;VALUE=DATE"] == "20270320"
    assert event["RRULE"] == "FREQ=YEARLY"
    assert "License renewal" in event["DESCRIPTION"]
    assert "Asdale Dynamics" in event["DESCRIPTION"]
