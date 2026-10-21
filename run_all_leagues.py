"""
Run the collector for every league in config.LEAGUES, for the current
season, one after another. Meant to run unattended (no CLI args, no
prompts) - all progress and per-league pass/fail results go to
run_all_leagues.log, so the run can be checked afterwards without
watching it live.

Usage:
    python run_all_leagues.py                    # every date of the season (original behaviour)
    python run_all_leagues.py --recent-days 7    # last 7 days + played games still missing xG

Always prints one final line to stdout, `SUMMARY_JSON {...}`, with per-league results, and exits 1 if
any league failed -- so a caller (the betting engine's cloud pipeline) can read the outcome without
parsing the log file.
"""

import argparse
import contextlib
import datetime
import json
import sys
import traceback

import config
import db
import collector

LOG_PATH = "run_all_leagues.log"


def current_season() -> str:
    """
    European league seasons start around August, so treat the season as
    having started this calendar year from July onward, and last
    calendar year for the rest of the year (e.g. Feb 2027 is still
    reported as season "2026").
    """
    today = datetime.date.today()
    year = today.year if today.month >= 7 else today.year - 1
    return str(year)


def main():
    parser = argparse.ArgumentParser(description="Run the collector for every league")
    parser.add_argument("--recent-days", type=int, default=None,
                        help="only fetch the last N days plus played games still missing xG")
    args = parser.parse_args()
    season = current_season()
    started_at = datetime.datetime.now()

    with open(LOG_PATH, "a", encoding="utf-8") as log:
        log.write(f"\n=== Run started {started_at.isoformat()} (season {season}) ===\n")
        log.flush()

        config.check_config()
        db.init_db()

        results = []
        errors = {}
        for league_name in config.LEAGUES:
            league_started = datetime.datetime.now()
            log.write(f"\n--- {league_name} ({season}) started {league_started.isoformat()} ---\n")
            log.flush()
            try:
                with contextlib.redirect_stdout(log):
                    collector.collect_league_season(league_name, season, recent_days=args.recent_days)
                results.append((league_name, "SUCCESS"))
                log.write(f"--- {league_name}: SUCCESS ---\n")
            except Exception as e:
                results.append((league_name, "FAILED"))
                errors[league_name] = str(e)[:300]
                log.write(f"--- {league_name}: FAILED - {e} ---\n")
                log.write(traceback.format_exc())
            log.flush()

        finished_at = datetime.datetime.now()
        succeeded = [name for name, status in results if status == "SUCCESS"]
        failed = [name for name, status in results if status == "FAILED"]

        log.write(f"\n=== Run finished {finished_at.isoformat()} (took {finished_at - started_at}) ===\n")
        log.write(f"Succeeded ({len(succeeded)}): {', '.join(succeeded) if succeeded else 'none'}\n")
        log.write(f"Failed ({len(failed)}): {', '.join(failed) if failed else 'none'}\n")
        log.flush()

    print("SUMMARY_JSON " + json.dumps({"season": season, "recent_days": args.recent_days,
                                        "succeeded": succeeded, "failed": failed, "errors": errors,
                                        "seconds": round((finished_at - started_at).total_seconds())}))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
