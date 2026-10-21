"""
SQLite helpers for the shared match-keyed store.
"""

import sqlite3
from pathlib import Path
from datetime import datetime, timezone
from config import DB_PATH


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    with open(Path(__file__).parent / "schema.sql") as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()


def upsert_match(conn, match: dict):
    """
    Insert a new match row, or update an existing one (matched on
    fixture_id) with whatever new fields are provided.
    """
    match = dict(match)  # don't mutate caller's dict
    match["collected_at"] = datetime.now(timezone.utc).isoformat()

    columns = list(match.keys())
    placeholders = ", ".join(f":{c}" for c in columns)
    updates = ", ".join(f"{c}=excluded.{c}" for c in columns if c != "fixture_id")

    sql = f"""
        INSERT INTO matches ({', '.join(columns)})
        VALUES ({placeholders})
        ON CONFLICT(fixture_id) DO UPDATE SET {updates}
    """
    conn.execute(sql, match)


def get_matches_missing_xg(conn, league_id: int, season: str) -> list[sqlite3.Row]:
    """Matches that still need Sportmonks data pulled for them."""
    cursor = conn.execute(
        """
        SELECT * FROM matches
        WHERE league_id = ? AND season = ?
        AND (sportmonks_match_status IS NULL OR sportmonks_match_status = 'not_fetched')
        """,
        (league_id, season),
    )
    return cursor.fetchall()


def get_matches_missing_weather(conn, league_id: int, season: str) -> list[sqlite3.Row]:
    cursor = conn.execute(
        """
        SELECT * FROM matches
        WHERE league_id = ? AND season = ?
        AND (weather_status IS NULL OR weather_status = 'not_fetched')
        """,
        (league_id, season),
    )
    return cursor.fetchall()
