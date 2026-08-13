"""
Central config for the collector.

Keys are read from environment variables, never hardcoded.
Create a `.env` file (see .env.example) in this folder and it will be
loaded automatically. Never commit your real .env file to git.
"""

import os
from pathlib import Path

# --- Load .env if present (optional, keeps local dev simple) ---
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # dotenv not installed - fine, will just rely on real env vars
    pass

# --- API-Football ---
# Direct api-football.com subscription uses the 'x-apisports-key' header.
API_FOOTBALL_KEY = os.environ.get("API_FOOTBALL_KEY")
API_FOOTBALL_BASE_URL = "https://v3.football.api-sports.io"

# --- Sportmonks ---
SPORTMONKS_TOKEN = os.environ.get("SPORTMONKS_TOKEN")
SPORTMONKS_BASE_URL = "https://api.sportmonks.com/v3/football"

# --- Open-Meteo ---
# No key needed at all.
OPEN_METEO_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"

# --- Storage ---
DB_PATH = Path(__file__).parent / "shared_data.db"

# --- Your 7 leagues: API-Football league IDs ---
# These are API-Football's standard league IDs - double check against
# your existing API-Football setup, since these can occasionally be
# provider-specific and I can't verify them live from here.
LEAGUES = {
    "Premier League": 39,
    "Championship": 40,
    "Bundesliga": 78,
    "La Liga": 140,
    "Serie A": 135,
    "Ligue 1": 61,
    "Eredivisie": 88,
}


def check_config():
    """Quick sanity check before running anything for real."""
    missing = []
    if not API_FOOTBALL_KEY:
        missing.append("API_FOOTBALL_KEY")
    if not SPORTMONKS_TOKEN:
        missing.append("SPORTMONKS_TOKEN")
    if missing:
        raise RuntimeError(
            f"Missing required environment variable(s): {', '.join(missing)}. "
            f"Set them in a .env file or your shell environment before running."
        )
    return True
