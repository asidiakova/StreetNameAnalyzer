import os
import psycopg2

from src.config import DB_TABLE


def get_osm_metadata() -> dict:
    """Collect OSM dataset metadata from the database.

    Returns a dict with:
        osm_data_date       - date the OSM data was loaded (from osm_metadata table)
        total_street_names  - unique street names in the dataset
        etymology_tagged    - unique street names that have a Wikidata etymology tag
    """
    result = {
        "osm_data_date": None,
        "total_street_names": None,
        "etymology_tagged": None,
    }
    db_conn_str = os.getenv("DATABASE_URL")
    if not db_conn_str:
        return result
    try:
        conn = psycopg2.connect(db_conn_str)
        cur = conn.cursor()

        try:
            cur.execute("SELECT value FROM osm_metadata WHERE key = 'data_date'")
            row = cur.fetchone()
            result["osm_data_date"] = row[0] if row else None
        except Exception:
            conn.rollback()

        cur.execute(f"""
            SELECT
                COUNT(DISTINCT name) AS total,
                COUNT(DISTINCT CASE
                    WHEN tags->'name:etymology:wikidata' IS NOT NULL
                    THEN name END) AS tagged
            FROM {DB_TABLE}
            WHERE name IS NOT NULL AND highway IS NOT NULL
        """)
        row = cur.fetchone()
        if row:
            result["total_street_names"] = row[0]
            result["etymology_tagged"] = row[1]

        conn.close()
    except Exception:
        pass
    return result
