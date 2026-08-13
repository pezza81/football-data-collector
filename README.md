# Post-match data collector

Pulls xG/Pressure Index (Sportmonks) and weather (Open-Meteo) onto your
existing API-Football fixtures, into one shared SQLite store keyed by
`fixture_id`.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# edit .env and add your real API_FOOTBALL_KEY and SPORTMONKS_TOKEN
```

## Before running the real backfill

Two things to verify first, flagged in the code with TODO comments:

1. **`sportmonks_client.py` - INCLUDES and field names.** I built this
   against Sportmonks' general v3 response pattern, but I couldn't test
   it against a live response from here. Pull one real fixture with the
   xG/Pressure Index bundle enabled (via MySportmonks' API tester or
   their Postman collection) and confirm the include names and field
   paths match what's in `parse_fixture()`.

2. **`api_football_client.py` - venue lat/lon.** Check whether the
   `/fixtures` response already includes venue coordinates, or whether
   you need the separate `/venues` lookup (`get_venue_coordinates()` is
   there as a fallback if so).

Run a small dry run first to sanity-check both:

```bash
python collector.py backfill --league "Premier League" --season 2022 --dry-run
```

This fetches and matches everything without writing to the database,
so you can inspect what's coming back before committing to a real run.

## Running for real

**Backfill** (once per league/season, for 2022-2025):

```bash
python collector.py backfill --league "Premier League" --season 2022
python collector.py backfill --league "Premier League" --season 2023
# ...repeat per league/season
```

**Live** (run weekly, post-gameweek, once 2026-27 is underway):

```bash
python collector.py live --league "Premier League" --season 2026
```

## Team name matching

Sportmonks and API-Football don't share fixture IDs, so matches are
found by date + team name similarity (`team_matcher.py`). It's been
tested against common cases (abbreviations like "Man United", and
distinct clubs sharing a suffix like "Leeds United" vs "Newcastle
United"), but real-world data will surface edge cases. If you notice a
team consistently failing to match during the backfill, add it to
`TEAM_ALIASES` or `WORD_ALIASES` in `team_matcher.py` rather than
relying on the fuzzy fallback.

Rows where no Sportmonks match was found are kept with
`sportmonks_match_status = 'unmatched'` rather than silently dropped -
worth spot-checking these after each league/season backfill.

## What this does NOT do

- Does not touch or duplicate your existing API-Football core stats
  pipeline - that keeps running exactly as it does now.
- Does not include historical data older than 3 seasons on Sportmonks'
  side unless you've bought the historical data add-on.
- Does not yet feed the fantasy app or Module E directly - this just
  builds the shared store. Wiring it into each is a separate next step.
