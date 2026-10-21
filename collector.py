"""
Main collector.

Two modes:

  Backfill (run once per league/season to fill in historical data):
      python collector.py backfill --league "Premier League" --season 2022

  Live (run weekly, post-gameweek, for the current season):
      python collector.py live --league "Premier League" --season 2026

Recent mode (used by run_all_leagues.py --recent-days N): instead of re-fetching every date of the
season, only fetch Sportmonks/weather for match dates in the last N days, plus the date of any game
already played that still has no xG on file. Fixture rows themselves are always refreshed (one
API-Football call per league), so kick-off changes are still picked up.

Fills in xG/Pressure Index (Sportmonks) and weather (Open-Meteo) onto
API-Football fixtures, joined into one shared store (shared_data.db).

Run `python collector.py backfill --league "Premier League" --season 2022 --dry-run`
first on a small slice to sanity-check matching before running the full backfill.
"""

import argparse
import datetime
import sys
import time

import config
import db
import api_football_client
import sportmonks_client
import openmeteo_client
import team_matcher


def dates_to_fetch(fixtures, missing_xg_ids, today, recent_days):
    """Match dates whose Sportmonks/weather data should be (re)fetched.

    recent_days=None -> every date in the season (the original full behaviour). Otherwise: dates from
    `today - recent_days` up to `today`, plus the date of any fixture already played (match_date <=
    today) whose fixture_id is in `missing_xg_ids` (no xG on file yet). Future dates are never
    fetched in recent mode -- there is nothing to collect for a game not yet played."""
    all_dates = {f["match_date"] for f in fixtures if f["match_date"]}
    if recent_days is None:
        return sorted(all_dates)
    today_s = today.isoformat()
    start_s = (today - datetime.timedelta(days=recent_days)).isoformat()
    wanted = {d for d in all_dates if start_s <= d <= today_s}
    wanted |= {f["match_date"] for f in fixtures
               if f["match_date"] and f["match_date"] <= today_s and f["fixture_id"] in missing_xg_ids}
    return sorted(wanted)


def collect_league_season(league_name: str, season: str, dry_run: bool = False, recent_days: int | None = None):
    league_id = config.LEAGUES.get(league_name)
    if league_id is None:
        print(f"Unknown league '{league_name}'. Valid options: {list(config.LEAGUES)}")
        sys.exit(1)

    print(f"\n=== {league_name} ({season}) ===")

    print("Fetching fixtures from API-Football...")
    fixtures = api_football_client.get_fixtures(league_id, season)
    print(f"  {len(fixtures)} fixtures found.")

    conn = db.get_connection()

    on_file = {r[0]: r[1] for r in conn.execute(
        "SELECT fixture_id, home_xg FROM matches WHERE league_id = ? AND season = ?", (league_id, season))}
    missing_xg_ids = {fid for fid, xg in on_file.items() if xg is None} | (
        {f["fixture_id"] for f in fixtures} - set(on_file))

    for af_fixture in fixtures:
        record = dict(af_fixture)
        # Full mode resets both statuses on every row (original behaviour). Recent mode only sets them
        # on rows not yet on file, so a row's existing status is never wiped for a date not re-fetched.
        if recent_days is None or af_fixture["fixture_id"] not in on_file:
            record["sportmonks_match_status"] = "not_fetched"
            record["weather_status"] = "not_fetched"

        if not dry_run:
            db.upsert_match(conn, record)

    conn.commit()

    # --- Sportmonks pass: fetch per unique date, match onto fixtures ---
    unique_dates = dates_to_fetch(fixtures, missing_xg_ids, datetime.date.today(), recent_days)
    mode = "all" if recent_days is None else f"recent ({recent_days} days + played games missing xG)"
    print(f"Fetching Sportmonks xG/Pressure Index for {len(unique_dates)} match dates [{mode}]...")

    for date in unique_dates:
        try:
            sm_fixtures = sportmonks_client.get_fixtures_by_date(date)
        except Exception as e:
            print(f"  Sportmonks fetch failed for {date}: {e}")
            continue

        day_af_fixtures = [f for f in fixtures if f["match_date"] == date]
        for af_fixture in day_af_fixtures:
            match = team_matcher.find_match(af_fixture, sm_fixtures)
            if match:
                update = dict(match)
                update["fixture_id"] = af_fixture["fixture_id"]
                update["sportmonks_match_status"] = "matched"
                if not dry_run:
                    db.upsert_match(conn, {
                        "fixture_id": af_fixture["fixture_id"],
                        "sportmonks_fixture_id": update.get("sportmonks_fixture_id"),
                        "home_xg": update.get("home_xg"),
                        "away_xg": update.get("away_xg"),
                        "home_xgot": update.get("home_xgot"),
                        "away_xgot": update.get("away_xgot"),
                        "home_npxg": update.get("home_npxg"),
                        "away_npxg": update.get("away_npxg"),
                        "home_xpts": update.get("home_xpts"),
                        "away_xpts": update.get("away_xpts"),
                        "home_pressure_index": update.get("home_pressure_index"),
                        "away_pressure_index": update.get("away_pressure_index"),
                        "sportmonks_match_status": "matched",
                    })
            else:
                if not dry_run:
                    db.upsert_match(conn, {
                        "fixture_id": af_fixture["fixture_id"],
                        "sportmonks_match_status": "unmatched",
                    })

        conn.commit()
        time.sleep(0.5)  # basic politeness delay between date requests

    # --- Weather pass ---
    print("Fetching weather from Open-Meteo...")
    date_set = set(unique_dates)
    for af_fixture in [f for f in fixtures if f["match_date"] in date_set]:
        weather = openmeteo_client.get_weather(
            af_fixture.get("venue_lat"),
            af_fixture.get("venue_lon"),
            af_fixture["match_date"],
        )
        if not dry_run:
            db.upsert_match(conn, {
                "fixture_id": af_fixture["fixture_id"],
                **weather,
            })
        time.sleep(0.2)

    conn.commit()
    conn.close()
    print(f"Done: {league_name} ({season}).")


def main():
    parser = argparse.ArgumentParser(description="Post-match data collector")
    parser.add_argument("mode", choices=["backfill", "live"])
    parser.add_argument("--league", required=True, help="League name, e.g. 'Premier League'")
    parser.add_argument("--season", required=True, help="Season, e.g. '2022'")
    parser.add_argument("--dry-run", action="store_true", help="Fetch and match without writing to DB")
    args = parser.parse_args()

    config.check_config()
    db.init_db()

    collect_league_season(args.league, args.season, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
