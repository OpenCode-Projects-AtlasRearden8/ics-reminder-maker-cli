# STATUS.md — ics-reminder-maker

Date: 2026-10-29
Maintainer: Asdale Dynamics, LLC

## What was built

**ics-reminder-maker** — a fully offline, standard-library-only Python CLI that
turns a plain `reminders.txt` into valid RFC 5545 (iCalendar 2.0) `.ics`
calendar files that every phone and desktop calendar can import:

- **All-day events** for each reminder (license renewal, insurance window,
  car registration, filter changes, library due dates — anything one line long).
- **Lead-time alerts**: `VALARM` alarms that fire N days before each event
  (`30,7,0` = 30 days out, 7 days out, and on the day).
- **Multi-day windows**: `2026-11-01..2026-11-30` becomes one all-day event
  spanning the window with an exclusive `DTEND` per the RFC.
- **Recurrence**: `yearly` / `monthly` via `RRULE:FREQ=YEARLY/MONTHLY`.
- **`--mega`**: a second, once-a-year file containing a recurring
  "Whole-Home Admin Day" event whose description carries a checklist of every
  reminder, chosen with `--admin-month`/`--admin-day` (defaults derived from
  the earliest reminder; impossible dates like Feb 30 slide to the last real
  day of the month; past dates advance to next year).
- Beginner-error handling: all broken lines reported at once, with line numbers.
- `--dry-run`, `--quiet`, `--year` filter, `--version`, and a helpful `--help`
  with a copy-pasteable example.

Companion to **dates-to-remember-mcp-server**: that MCP server lets AI assistants
answer questions about important dates; this tool turns the same reminders into
calendar files.

## How to run it

```bash
# install (Python 3.10+)
python -m pip install .

# run
ics-reminder-maker examples/reminders.txt -o outdir/ --mega
# or without installing:
python -m ics_reminder_maker examples/reminders.txt --mega
```

Reminder-line format: `Name | date | lead days | yearly/monthly | note`
(only name and date are required; `#` lines are comments). See `README.md`
and `examples/reminders.txt`.

## Project layout

- `ics_reminder_maker/parser.py` — reminders.txt parsing with full error collection
- `ics_reminder_maker/icsgen.py` — RFC 5545 generation: CRLF, 75-octet line
  folding, TEXT escaping, DATE values, exclusive DTEND, TRIGGER durations, UIDs
- `ics_reminder_maker/cli.py` — argparse CLI, output resolution, mega day logic
- `tests/` — pytest suite + fixtures (`tests/fixtures/*.txt`)
- `examples/reminders.txt` — starter reminders file
- `LICENSE` — MIT, "Copyright (c) 2026 Asdale Dynamics, LLC"
- `README.md` — user guide, credits Asdale Dynamics, LLC

## Verification results

- `python -m pytest tests/` → **47 passed** (parser, generator, CLI e2e via
  subprocess; structural RFC mini-parser asserts CRLF, folding ≤75 octets,
  balanced BEGIN/END, alarm triggers, escaping, UID stability/uniqueness).
- `pip install .` into a fresh venv → installs cleanly; console script
  `ics-reminder-maker --version` → `ics-reminder-maker 1.0.0`.
- Manual end-to-end run over `examples/reminders.txt` produced both files with
  the expected summaries, DTSTART/DTEND, RRULEs, alarm counts, and checklist text.
- Output inspected with `cat -A`: pure CRLF line endings, valid folding.

## Known gaps / future ideas

- Lead alerts repeat the same relative days for recurring events (that is how
  ICS triggers work); per-recurrence-varying lead times are not possible in
  the format.
- No `.ics` reading/import-back — output only.
- Mega day is a single yearly event, not per-reminder groupings by season.
- No localization (month/day names are numeric) — fine for calendar apps.
- Tests validate structure with an in-repo mini-parser rather than a third-
  party iCalendar library (kept stdlib-only and offline by design).
