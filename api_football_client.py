"""
API-Football client.

Only responsible for fetching fixture-level info needed to anchor the
shared store and to look up Sportmonks/weather data: fixture ID, date,
teams, league, and venue coordinates (for weather).

This does NOT duplicate your existing core-stats collection - that
pipeline keeps running exactly as it does now. This client only pulls
what's needed to drive the new supplementary sources.
"""

import requests
from config import API_FOOTBALL_KEY, API_FOOTBALL_BASE_URL

HEADERS = {"x-apisports-key": API_FOOTBALL_KEY}


def get_fixtures(league_id: int, season: str) -> list[dict]:
    """
    Fetch all fixtures for a league/season.

    Returns a list of dicts with the fields the rest of the collector
    needs: fixture_id, date, kickoff_utc, home_team, away_team,
    venue_name, venue_lat, venue_lon.
    """
    url = f"{API_FOOTBALL_BASE_URL}/fixtures"
    params = {"league": league_id, "season": season}

    resp = requests.get(url, headers=HEADERS, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    # API-Football reports errors (rate limits, bad params, etc.) as HTTP 200
    # with an "errors" object in the body, not as an HTTP error status - so
    # raise_for_status() alone won't catch them. Without this check, a
    # rate-limited call silently looks identical to "no fixtures this date".
    errors = data.get("errors")
    if errors:
        raise RuntimeError(f"API-Football returned errors for league={league_id} season={season}: {errors}")

    fixtures = []
    for item in data.get("response", []):
        fixture = item.get("fixture", {})
        league = item.get("league", {})
        teams = item.get("teams", {})
        venue = fixture.get("venue", {})

        fixtures.append({
            "fixture_id": fixture.get("id"),
            "league_id": league.get("id"),
            "league_name": league.get("name"),
            "season": str(season),
            "match_date": (fixture.get("date") or "")[:10],
            "kickoff_utc": fixture.get("date"),
            "home_team": teams.get("home", {}).get("name"),
            "away_team": teams.get("away", {}).get("name"),
            "venue_name": venue.get("name"),
            # NOTE: API-Football's fixtures endpoint does not always return
            # venue lat/lon directly - it may need a separate call to the
            # /venues endpoint keyed by venue id. Flagging this so it gets
            # checked against a real response before the backfill run.
            "venue_lat": venue.get("lat"),
            "venue_lon": venue.get("lon"),
        })

    return fixtures


def get_venue_coordinates(venue_id: int) -> dict:
    """
    Fallback lookup if venue lat/lon isn't included on the fixture response.
    Confirm whether this extra call is actually needed once you see a
    real fixtures response - if lat/lon is already present, skip this.
    """
    url = f"{API_FOOTBALL_BASE_URL}/venues"
    params = {"id": venue_id}
    resp = requests.get(url, headers=HEADERS, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if data.get("response"):
        venue = data["response"][0]
        return {"lat": venue.get("address", {}).get("lat"),
                "lon": venue.get("address", {}).get("lon")}
    return {"lat": None, "lon": None}
