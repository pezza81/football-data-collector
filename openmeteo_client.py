"""
Open-Meteo client.

No API key required. Fetches historical weather (temp, precipitation,
wind) for a venue's coordinates on a given date.
"""

import requests
from config import OPEN_METEO_ARCHIVE_URL


def get_weather(lat: float, lon: float, date: str) -> dict:
    """
    Fetch historical weather for a single date at a lat/lon.
    `date` should be YYYY-MM-DD.

    Returns hourly data - we pull the value closest to typical kickoff
    time (15:00 local as a reasonable default) since we don't always
    know exact kickoff hour at collection time. This can be refined
    later to match actual kickoff_utc per match if useful.
    """
    if lat is None or lon is None:
        return {"temp_c": None, "precip_mm": None, "wind_kph": None, "weather_status": "no_coordinates"}

    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": date,
        "end_date": date,
        "hourly": "temperature_2m,precipitation,wind_speed_10m",
        "timezone": "auto",
    }

    resp = requests.get(OPEN_METEO_ARCHIVE_URL, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    hourly = data.get("hourly", {})
    times = hourly.get("time", [])
    temps = hourly.get("temperature_2m", [])
    precip = hourly.get("precipitation", [])
    wind = hourly.get("wind_speed_10m", [])

    if not times:
        return {"temp_c": None, "precip_mm": None, "wind_kph": None, "weather_status": "not_found"}

    # Pick the hour closest to 15:00 local as a reasonable kickoff proxy
    target_hour = f"{date}T15:00"
    idx = min(range(len(times)), key=lambda i: abs(_hour_diff(times[i], target_hour)))

    return {
        "temp_c": temps[idx] if idx < len(temps) else None,
        "precip_mm": precip[idx] if idx < len(precip) else None,
        "wind_kph": wind[idx] if idx < len(wind) else None,
        "weather_status": "matched",
    }


def _hour_diff(t1: str, t2: str) -> int:
    """Rough string-based hour comparison, good enough for nearest-hour matching."""
    try:
        h1 = int(t1.split("T")[1].split(":")[0])
        h2 = int(t2.split("T")[1].split(":")[0])
        return h1 - h2
    except (IndexError, ValueError):
        return 0
