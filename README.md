# ics-reminder-maker

A tiny, friendly command-line tool that turns a plain `reminders.txt` file into
real, valid calendar files (`.ics`) — the kind every phone and desktop calendar
can open. No accounts, no syncing, no internet connection needed. Ever.

You write a list like this:

```
# name | date | lead-time alert days (optional) | yearly/monthly (optional) | note (optional)
License renewal | 2027-01-15 | 30,7,0 | yearly | Bring checkbook and ID
Insurance window | 2026-11-01..2026-11-30 | 14,7 | Compare quotes early
Car registration | 2026-12-01 | 30,0
Furnace filter change | 2027-03-01 | 0 | monthly | Filter size: MERV 11
Library books due | 2026-11-20 | 3,0
```

And this tool produces calendar events for every line — **all-day** events, with
**lead-time alert** alarms that pop up in your calendar the requested number of
days before each date. It can also make a once-a-year **Whole-Home Admin Day**:
one recurring event that carries a checklist of every home chore on your list,
so a single calendar entry reminds you to do the big annual sweep.

Made by and for people who find life admin overwhelming. It is designed to be
beginner-friendly, local-first, and completely transparent: everything happens
on your computer, in plain text files you can read, back up, and keep forever.

It pairs nicely with the companion project
**dates-to-remember-mcp-server** — that one lets AI assistants read and answer
questions about your important dates; this one turns those same reminders into
calendar files.

## How to use it

You need Python 3.10 or newer. That's it.

### Install

```bash
python -m pip install .
```

Or just run it straight from this folder:

```bash
python -m ics_reminder_maker my-reminders.txt
```

### Write your reminders

Create a text file (save it as UTF-8). One reminder per line, fields separated
by `|`:

```
Name | date | lead days | recurrence | note
```

- **Name** — anything you like (it can't contain a `|`).
- **date** — one day (`2026-11-15`) or a window (`2026-11-01..2026-11-30`).
- **lead days** — optional. Comma-separated days before the start when your
  calendar should alert you. `30,7,0` means "30 days before, 7 days before,
  and on the day". Leave it out and there are no alarms.
- **recurrence** — optional. `yearly`, `monthly`, or `none` (the default).
  Repeating events recur every year or month on that date.
- **note** — optional free text, kept in the event description.

Lines starting with `#` are comments. Blank lines are skipped. If something is
wrong, the tool tells you every broken line at once, with line numbers.

### Run it

```bash
# Most common: read my-reminders.txt, write my-reminders.ics next to it
ics-reminder-maker my-reminders.txt

# Choose where it goes (file or folder)
ics-reminder-maker my-reminders.txt -o calendar/

# Also create the once-a-year Whole-Home Admin Day file
ics-reminder-maker my-reminders.txt -o calendar/ --mega

# Pick the admin day yourself (falls to the last valid day of a short month)
ics-reminder-maker my-reminders.txt --mega --admin-month 3 --admin-day 20

# Filters: keep only reminders starting in a given year (repeating ones always stay)
ics-reminder-maker my-reminders.txt --year 2027

# Preview without writing anything
ics-reminder-maker my-reminders.txt --dry-run
```

See all options with `--help`. If you skip `-o`, the output lands in your
current folder as `<input-name>.ics`. With `--mega`, a second file named
`whole-home-admin-day.ics` is written next to it.

### Import into your calendar

Open Google Calendar, Apple Calendar/Reminders, Outlook, or GNOME/KDE calendar
apps and use their "Import" feature, or just double-click the `.ics` file on
your computer. All events are all-day and marked transparent, so they never
block your schedule — they just appear, calm and useful.

## Running the tests

```bash
python -m pytest tests/
```

The test suite is pure standard-library pytest with fixture files under
`tests/fixtures/`, so it runs offline just like the tool itself.

## Example files

- `examples/reminders.txt` — a starter file modeled on real home admin:
  license renewal, an insurance shopping window, car registration, furnace
  filter changes, and library due dates.

## Design notes

- **Offline and secret-free.** No network calls, no accounts, no telemetry,
  no keys. Your dates never leave your machine.
- **RFC 5545 compliant.** CRLF line endings, long lines folded to 75 octets,
  `TEXT` values escaped, exclusive `DTEND` for multi-day windows, and
  `TRIGGER;VALUE=DURATION` alarms — the parts calendar apps actually care about.
- **Boring on purpose.** One small Python package, standard library only.
  Easy to read, easy to keep working for years.

## Known limits

- Alerts repeat the same days for every recurrence (the trigger is relative to
  the event).
- Very long names and notes (> ~75 characters) get line-folded per the RFC —
  every real calendar app unfolds them correctly.

## License

MIT — see `LICENSE`. Built by **Asdale Dynamics, LLC**, the plain-English AI
education folks behind *The Massive AI Manual* (dylanasdale.github.io).
