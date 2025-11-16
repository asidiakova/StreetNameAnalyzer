#!/usr/bin/env python3

from __future__ import annotations
import argparse
import os
import sys
import psycopg2
from dotenv import load_dotenv

load_dotenv()

table = "planet_osm_line"


def parse_args():
    p = argparse.ArgumentParser(
        description="Aggregate street lengths by raw name using PostGIS. Choose EPSG 4326 (geography) or 5514 (Slovakia projected)."
    )
    p.add_argument("--db", "-d", required=False, default=os.getenv("DATABASE_URL"),
                   help="Postgres connection URI or use DATABASE_URL env var")
    p.add_argument("--limit", type=int, default=100,
                   help="Print only top N rows (no limit means full CSV if --out is provided)")
    p.add_argument("--out", default=None, help="Output CSV file path. If omitted, prints top rows to stdout.")
    p.add_argument("--epsg", type=int, default=4326,
                   help="Target EPSG code for length calculation (default: 4326). Supported: 4326, 5514(SK/CZ)")
    return p.parse_args()


def split_table(table: str):
    if '.' in table:
        schema, tbl = table.split('.', 1)
    else:
        schema, tbl = 'public', table
    return schema, tbl


def determine_length_expression(target_epsg: int) -> str:
    if target_epsg == 4326:
        return f"ST_Length(ST_Transform(way, {target_epsg})::geography)"
    else:
        return f"ST_Length(ST_Transform(way, {target_epsg}))"


def main():
    args = parse_args()
    if not args.db:
        print("Error: provide --db or set DATABASE_URL env var.", file=sys.stderr)
        sys.exit(2)

    if args.epsg not in (4326, 5514):
        print(
            "Warning: script tested for EPSG 4326 and 5514. Other EPSGs will be treated as 'projected' -- proceed with caution.",
            file=sys.stderr)

    schema, tbl = split_table(table)
    conn = psycopg2.connect(args.db)
    try:
        cur = conn.cursor()
        length_expr = determine_length_expression(args.epsg)

        # TODO: difference between highway types
        # https://skorasaurus.wordpress.com/2014/05/07/how-i-measured-clevelands-length-of-roads-with-postgis-and-osm/#:~:text=select%20highway%2C%20name%2C%20way%2C%20st_length,HOORAH
        sql = f"""
            SELECT name, SUM({length_expr}) AS total_m, COUNT(*) AS segments_count
            FROM {schema}.{tbl}
            WHERE name IS NOT NULL AND highway IS NOT NULL
            GROUP BY name
            ORDER BY total_m DESC
        """
        if args.limit and args.out is None:
            sql = sql + f" LIMIT {int(args.limit)}"

        if args.out:
            copy_sql = f"COPY ({sql}) TO STDOUT WITH CSV HEADER"
            with open(args.out, "w", newline='') as fh:
                cur.copy_expert(copy_sql, fh)
            print(f"Wrote results to {args.out}")
        else:
            cur.execute(sql)
            rows = cur.fetchall()
            for name, total_m, cnt in rows[:args.limit] if args.limit else rows:
                display_name = name if name is not None else "<NULL>"
                print(f"{total_m:.3f} m | {cnt} segments | {display_name}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
