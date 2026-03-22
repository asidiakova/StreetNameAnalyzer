#!/usr/bin/env python3

import argparse
import os
import psycopg2
from src.config import COMPUTE_OUTPUT_DEFAULT, UNTAGGED_OUTPUT_DEFAULT


def main():
    parser = argparse.ArgumentParser(
        description="Aggregate street lengths by raw name using PostGIS."
    )
    parser.add_argument("--limit", type=int, default=None,
                   help="Print only top N rows")
    parser.add_argument("--out", default=COMPUTE_OUTPUT_DEFAULT,
                   help="Output CSV file path. If omitted, prints top rows to stdout.")

    args = parser.parse_args()
    db_conn_str = os.getenv("DATABASE_URL")
    conn = psycopg2.connect(db_conn_str)
    try:
        cur = conn.cursor()
        # Streets in OSM are split into many small segments. ST_ClusterDBSCAN
        # groups segments within 100 m of each other (SRID 5514 = meters) so
        # that "Štúrova" in Bratislava and "Štúrova" in Košice count as two
        # separate streets, not one.
        sql = f"""
            SELECT name,
                   SUM(length_m)                AS total_m,
                   COUNT(*)                     AS segments_count,
                   COUNT(DISTINCT cluster_id)   AS street_count
            FROM (
                SELECT name,
                       ST_ClusterDBSCAN(ST_Transform(way, 5514), eps := 100, minpoints := 1)
                         OVER (PARTITION BY name) AS cluster_id,
                       ST_Length(ST_Transform(way, 4326)::geography) AS length_m
                FROM planet_osm_line
                WHERE name IS NOT NULL AND highway IS NOT NULL
            ) clustered
            GROUP BY name
            ORDER BY total_m DESC
        """
        if args.limit and args.out is None:
            sql = sql + f" LIMIT {int(args.limit)}"

        if args.out:
            copy_sql = f"COPY ({sql}) TO STDOUT WITH CSV HEADER"
            with open(args.out, "w", newline='', encoding="utf-8") as fh:
                cur.copy_expert(copy_sql, fh)
            print(f"Wrote results to {args.out}")
        else:
            cur.execute(sql)
            rows = cur.fetchall()
            for name, total_m, seg_cnt, st_cnt in rows[:args.limit] if args.limit else rows:
                display_name = name if name is not None else "<NULL>"
                print(f"{total_m:.3f} m | {seg_cnt} segments | {st_cnt} streets | {display_name}")

        untagged_sql = f"""
            SELECT DISTINCT name
            FROM planet_osm_line
            WHERE name IS NOT NULL
              AND highway IS NOT NULL
              AND (tags->'name:etymology:wikidata') IS NULL
            ORDER BY name
        """
        copy_untagged = f"COPY ({untagged_sql}) TO STDOUT WITH CSV HEADER"
        with open(UNTAGGED_OUTPUT_DEFAULT, "w", newline='', encoding="utf-8") as fh:
            cur.copy_expert(copy_untagged, fh)
        print(f"Wrote untagged streets to {UNTAGGED_OUTPUT_DEFAULT}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
