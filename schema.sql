-- Shared post-match data store
-- Join key across all sources: fixture_id (API-Football's fixture ID)
-- One row per match. Sportmonks and Open-Meteo data get matched onto
-- the API-Football fixture via date + team names (see team_matcher.py).

CREATE TABLE IF NOT EXISTS matches (
    fixture_id INTEGER PRIMARY KEY,   -- API-Football fixture ID (the shared key)
    league_id INTEGER,
    league_name TEXT,
    season TEXT,                      -- e.g. '2022', '2023'
    match_date TEXT,                  -- ISO date, YYYY-MM-DD
    kickoff_utc TEXT,
    home_team TEXT,
    away_team TEXT,
    venue_name TEXT,
    venue_lat REAL,
    venue_lon REAL,

    -- Sportmonks: xG / advanced metrics
    home_xg REAL,
    away_xg REAL,
    home_xgot REAL,
    away_xgot REAL,
    home_npxg REAL,
    away_npxg REAL,
    home_xpts REAL,
    away_xpts REAL,
    home_pressure_index REAL,
    away_pressure_index REAL,
    sportmonks_fixture_id INTEGER,
    sportmonks_match_status TEXT,     -- 'matched' | 'unmatched' | 'not_fetched'

    -- Open-Meteo: weather at kickoff
    temp_c REAL,
    precip_mm REAL,
    wind_kph REAL,
    weather_status TEXT,              -- 'matched' | 'not_fetched'

    collected_at TEXT                 -- timestamp this row was last updated
);

CREATE INDEX IF NOT EXISTS idx_matches_date ON matches(match_date);
CREATE INDEX IF NOT EXISTS idx_matches_league_season ON matches(league_id, season);
