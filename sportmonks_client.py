"""
Sportmonks client.

Fetches xG, xGoT, npxG, xPTS, and Pressure Index for a given date/league.

Verified against the live v3 API on 2026-08-13:
  - Include name is "pressure", not "pressureIndex" (that 404s with
    error code 5001 - "include does not exist").
  - Response keys come back lowercase: "xgfixture" and "pressure",
    not "xGFixture"/"pressureIndex" as requested.
  - "xgfixture" is a flat list of per-metric entries (one per team per
    stat type), tagged with a type_id. Relevant type_ids (looked up via
    GET /v3/core/types/{id}):
      5304 = Expected Goals (xG)
      5305 = Expected Goals on Target (xGoT)
      7943 = Expected Goals Non Penalty Goals (npxG)
      7939 = Expected Points (xPTS)
  - "pressure" is a per-minute time series per participant_id (no
    home/away label on each entry), not a home/away aggregate. This
    client averages it per team to produce a single pressure index,
    matching the single REAL column per side in schema.sql.
  - "participants" must be explicitly included or team names (used by
    team_matcher for date+name matching) come back empty and nothing
    ever matches.
  - The endpoint paginates at 25 fixtures per page ("has_more"/
    "next_page" in the response). On dates with many leagues playing
    at once (e.g. Saturday fixtures), the real match set is well past
    25, so fetching only page 1 silently drops fixtures - this showed
    up as a much lower match rate for La Liga (busy dates) than for
    leagues with fewer simultaneous fixtures. get_fixtures_by_date()
    now follows "next_page" until "has_more" is false.
"""

import requests
from config import SPORTMONKS_TOKEN, SPORTMONKS_BASE_URL

INCLUDES = "xGFixture;pressure;participants"

XG_TYPE_IDS = {
    5304: "xg",
    5305: "xgot",
    7943: "npxg",
    7939: "xpts",
}


def get_fixtures_by_date(date: str, league_id: int | None = None) -> list[dict]:
    """
    Fetch Sportmonks fixtures for a given date (YYYY-MM-DD), with
    xG/Pressure Index data attached via includes.
    """
    url = f"{SPORTMONKS_BASE_URL}/fixtures/date/{date}"
    headers = {
        "Authorization": SPORTMONKS_TOKEN,
    }
    params = {
        "include": INCLUDES,
    }
    if league_id:
        params["filters"] = f"fixtureLeagues:{league_id}"

    all_raw_fixtures = []
    next_url = url
    next_params = params
    while next_url:
        resp = requests.get(next_url, headers=headers, params=next_params, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        all_raw_fixtures.extend(data.get("data", []))

        pagination = data.get("pagination", {})
        next_url = pagination.get("next_page") if pagination.get("has_more") else None
        next_params = None  # next_page URL already has query params baked in

    return [parse_fixture(f) for f in all_raw_fixtures]


def parse_fixture(raw: dict) -> dict:
    """Pull out the fields we actually need from a raw Sportmonks fixture."""
    participants = raw.get("participants", []) or []
    home = next((p for p in participants if p.get("meta", {}).get("location") == "home"), {})
    away = next((p for p in participants if p.get("meta", {}).get("location") == "away"), {})

    metrics = {}
    for entry in raw.get("xgfixture", []) or []:
        key = XG_TYPE_IDS.get(entry.get("type_id"))
        location = entry.get("location")
        if key and location in ("home", "away"):
            value = (entry.get("data") or {}).get("value")
            metrics[f"{location}_{key}"] = value

    pressure_by_participant = {home.get("id"): "home", away.get("id"): "away"}
    pressure_totals = {"home": [], "away": []}
    for entry in raw.get("pressure", []) or []:
        location = pressure_by_participant.get(entry.get("participant_id"))
        value = entry.get("pressure")
        if location and value is not None:
            pressure_totals[location].append(value)

    def avg(values):
        return sum(values) / len(values) if values else None

    return {
        "sportmonks_fixture_id": raw.get("id"),
        "match_date": (raw.get("starting_at") or "")[:10],
        "home_team": home.get("name"),
        "away_team": away.get("name"),
        "home_xg": metrics.get("home_xg"),
        "away_xg": metrics.get("away_xg"),
        "home_xgot": metrics.get("home_xgot"),
        "away_xgot": metrics.get("away_xgot"),
        "home_npxg": metrics.get("home_npxg"),
        "away_npxg": metrics.get("away_npxg"),
        "home_xpts": metrics.get("home_xpts"),
        "away_xpts": metrics.get("away_xpts"),
        "home_pressure_index": avg(pressure_totals["home"]),
        "away_pressure_index": avg(pressure_totals["away"]),
    }
