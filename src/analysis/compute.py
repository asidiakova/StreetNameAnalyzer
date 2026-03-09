#!/usr/bin/env python3

from __future__ import annotations
import argparse
import os
import psycopg2
from src.config import DB_TABLE, COMPUTE_OUTPUT_DEFAULT


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
        sql = f"""
            SELECT name, SUM(ST_Length(ST_Transform(way, 4326)::geography)) AS total_m, COUNT(*) AS segments_count
            FROM public.{DB_TABLE}
            WHERE name IS NOT NULL AND highway IS NOT NULL
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
            for name, total_m, cnt in rows[:args.limit] if args.limit else rows:
                display_name = name if name is not None else "<NULL>"
                print(f"{total_m:.3f} m | {cnt} segments | {display_name}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
