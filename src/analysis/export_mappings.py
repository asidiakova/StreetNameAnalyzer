#!/usr/bin/env python3
"""
Export normalization mappings as JSON for the frontend application.

Reads unique street names from output produced by compute.py,
runs each normalization method, and outputs a JSON file containing:
- mapping: street_name -> canonical_name
- groups: canonical_name -> {representative, total_length, variants}
"""

import argparse
import csv
import json
from datetime import datetime, timezone
from typing import Callable

from src.config import COMPUTE_OUTPUT_DEFAULT, MAPPINGS_OUTPUT_DEFAULT
from src.normalization_methods import NORMALIZATION_METHODS
from src.analysis import get_osm_metadata


def load_street_names(input_csv: str) -> list[tuple[str, float, int, int]]:
    """Load unique street names with lengths from compute.py output."""
    rows = []
    with open(input_csv, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader, None)
        for line in reader:
            if len(line) < 4:
                continue
            name = line[0].strip()
            length = float(line[1])
            segments = int(line[2])
            streets = int(line[3])
            rows.append((name, length, segments, streets))
    return rows


def build_method_data(
    normalize_fn: Callable[[str], str],
    street_data: list[tuple[str, float, int, int]],
) -> dict:
    """Run a normalization method and produce mapping + group statistics."""
    mapping = {}
    groups = {}

    for name, length, segments, streets in street_data:
        canonical = normalize_fn(name)
        if not canonical:
            continue

        mapping[name] = canonical

        if canonical not in groups:
            groups[canonical] = {
                "representative": None,
                "total_length": 0.0,
                "segment_count": 0,
                "street_count": 0,
                "variants": [],
                "_max_length": 0.0,
            }

        g = groups[canonical]
        g["total_length"] += length
        g["segment_count"] += segments
        g["street_count"] += streets
        g["variants"].append(name)

        if length > g["_max_length"]:
            g["_max_length"] = length
            g["representative"] = name

    for g in groups.values():
        del g["_max_length"]
        g["total_length"] = round(g["total_length"], 1)

    return {"mapping": mapping, "groups": groups}


def main():
    parser = argparse.ArgumentParser(description="Export normalization mappings as JSON")
    parser.add_argument("--input", "-i", default=COMPUTE_OUTPUT_DEFAULT,
                        help="Input CSV from compute.py")
    parser.add_argument("--out", "-o", default=MAPPINGS_OUTPUT_DEFAULT,
                        help="Output JSON path")
    args = parser.parse_args()

    print(f"Loading street names from {args.input}...")
    street_data = load_street_names(args.input)
    print(f"Loaded {len(street_data)} unique street names")

    all_names = [name for name, _, _, _ in street_data]

    osm_meta = get_osm_metadata()
    result = {
        "_metadata": {
            **osm_meta,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
    }
    for method_name, normalize_fn in NORMALIZATION_METHODS:
        print(f"Running method: {method_name}...")
        if hasattr(normalize_fn, "batch_warm"):
            normalize_fn.batch_warm(all_names)
        result[method_name] = build_method_data(normalize_fn, street_data)
        n_groups = len(result[method_name]["groups"])
        print(f"  {len(result[method_name]['mapping'])} names -> {n_groups} groups")

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\nMappings written to {args.out}")


if __name__ == "__main__":
    main()
