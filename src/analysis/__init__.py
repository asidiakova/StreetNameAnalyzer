import os
import psycopg2

def get_osm_metadata() -> dict:
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
            FROM planet_osm_line
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
