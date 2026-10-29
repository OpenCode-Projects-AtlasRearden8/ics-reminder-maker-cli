"""End-to-end CLI tests run as subprocesses with real fixture files."""

from __future__ import annotations

import subprocess
import sys

import pytest

from ics_reminder_maker.parser import parse_reminders

from helpers import FIXTURES, parse_calendar, read_bytes_text, read_fixture


def run_cli(*args: str, cwd: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "ics_reminder_maker", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
    )


def test_writes_default_output_next_to_cwd(tmp_path):
    result = run_cli(str(FIXTURES / "reminders_simple.txt"), "-o", str(tmp_path))
    assert result.returncode == 0, result.stderr
    out = tmp_path / "reminders_simple.ics"
    assert out.is_file()
    text = read_bytes_text(out)
    cal = parse_calendar(text)
    assert len(cal["events"]) == 5
    assert "Wrote" in result.stdout
    assert "5 event(s), 10 alert(s)" in result.stdout


def test_explicit_output_file(tmp_path):
    result = run_cli(
        str(FIXTURES / "reminders_simple.txt"), "-o", str(tmp_path / "mine.ics")
    )
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "mine.ics").is_file()
    assert not (tmp_path / "reminders_simple.ics").exists()


def test_mega_creates_annual_admin_day_file(tmp_path):
    result = run_cli(str(FIXTURES / "reminders_simple.txt"), "-o", str(tmp_path), "--mega")
    assert result.returncode == 0, result.stderr
    mega = tmp_path / "whole-home-admin-day.ics"
    assert mega.is_file()
    cal = parse_calendar(read_bytes_text(mega))
    assert len(cal["events"]) == 1
    event = cal["events"][0]
    assert event["SUMMARY"] == "Whole-Home Admin Day"
    assert event["DTSTART;VALUE=DATE"] == "20261101"
    assert event["RRULE"] == "FREQ=YEARLY"


def test_mega_admin_day_flag(tmp_path):
    result = run_cli(
        str(FIXTURES / "reminders_simple.txt"),
        "-o",
        str(tmp_path),
        "--mega",
        "--admin-month",
        "3",
        "--admin-day",
        "14",
        "-q",
    )
    assert result.returncode == 0, result.stderr
    mega = read_bytes_text(tmp_path / "whole-home-admin-day.ics")
    assert "DTSTART;VALUE=DATE:20270314" in mega


def test_admin_day_falls_back_to_last_valid_day(tmp_path):
    result = run_cli(
        str(FIXTURES / "reminders_simple.txt"),
        "-o",
        str(tmp_path),
        "--mega",
        "--admin-month",
        "2",
        "--admin-day",
        "31",
    )
    assert result.returncode == 0
    assert "no day 31 in month 2" in (result.stdout + result.stderr)
    assert "DTSTART;VALUE=DATE:20270228" in read_bytes_text(
        tmp_path / "whole-home-admin-day.ics"
    )


def test_year_filter_keeps_recurring(tmp_path):
    result = run_cli(
        str(FIXTURES / "reminders_simple.txt"),
        "-o",
        str(tmp_path),
        "--year",
        "2027",
        "-q",
    )
    assert result.returncode == 0
    cal = parse_calendar(read_bytes_text(tmp_path / "reminders_simple.ics"))
    names = [ev["SUMMARY"] for ev in cal["events"]]
    assert names == ["License renewal", "Furnace filter change"]


def test_year_filter_with_no_matches_fails(tmp_path):
    result = run_cli(
        str(FIXTURES / "reminders_errors.txt"),
        "-o",
        str(tmp_path),
        "--year",
        "2999",
    )
    assert result.returncode == 1


def test_parse_errors_exit_nonzero_and_list_lines():
    result = run_cli(str(FIXTURES / "reminders_errors.txt"))
    assert result.returncode == 1
    assert "line 2" in result.stderr
    assert "line 8" in result.stderr
    assert "line 1" not in result.stderr


def test_missing_input_file():
    result = run_cli(str(FIXTURES / "does_not_exist.txt"))
    assert result.returncode == 2
    assert "not found" in result.stderr


def test_dry_run_writes_nothing(tmp_path):
    result = run_cli(
        str(FIXTURES / "reminders_simple.txt"),
        "-o",
        str(tmp_path),
        "--dry-run",
    )
    assert result.returncode == 0, result.stderr
    assert list(tmp_path.iterdir()) == []
    assert "Would write" in result.stdout


def test_quiet_writes_but_prints_nothing(tmp_path):
    result = run_cli(
        str(FIXTURES / "reminders_single.txt"), "-o", str(tmp_path), "-q"
    )
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "reminders_single.ics").is_file()
    assert result.stdout == ""


def test_version_flag():
    result = run_cli("--version")
    assert result.returncode == 0
    assert result.stdout.startswith("ics-reminder-maker")


def test_help_shows_example():
    result = run_cli("--help")
    assert result.returncode == 0
    assert "reminders.txt" in result.stdout, "help output should mention reminders.txt"
    assert "License renewal" in result.stdout, "help output should show the example"


def test_examples_file_round_trip(tmp_path):
    example = FIXTURES.parent.parent / "examples" / "reminders.txt"
    result = run_cli(str(example), "-o", str(tmp_path), "--mega")
    assert result.returncode == 0, result.stderr
    expected = parse_reminders(read_fixture("reminders_simple.txt"))
    assert len(expected) == 5
