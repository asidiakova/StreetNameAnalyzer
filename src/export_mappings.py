#!/usr/bin/env python3
"""
Export normalization mappings as JSON for the frontend application.

Reads unique street names from output.csv (produced by compute.py),
runs each normalization method, and outputs a JSON file containing:
- mapping: street_name → canonical_name (for coloring map segments)
- groups: canonical_name → {representative, total_length, variants} (for statistics)

Usage:
    python export_mappings.py                       # uses default output.csv
    python export_mappings.py --input output.csv    # explicit input
    python export_mappings.py --out mappings.json   # custom output path
"""

import argparse
import csv
import json
from typing import Callable

from config import COMPUTE_OUTPUT_DEFAULT
from normalize import normalize_key


# Registry of normalization methods.
# Add new methods here as: ("method_name", normalize_function)
METHODS: list[tuple[str, Callable[[str], str]]] = [
    ("suffix_stripping", normalize_key),
]


def load_street_names(input_csv: str) -> list[tuple[str, float, int]]:
    """Load unique street names with lengths from compute.py output."""
    rows = []
    with open(input_csv, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader, None)  # skip header
        for line in reader:
            if len(line) < 3:
                continue
            name = line[0].strip()
            length = float(line[1])
            segments = int(line[2])
            rows.append((name, length, segments))
    return rows


def build_method_data(
    normalize_fn: Callable[[str], str],
    street_data: list[tuple[str, float, int]],
) -> dict:
    """
    Run a normalization method and produce mapping + group statistics.

    Returns:
        {
            "mapping": {"Štefánikova": "stefan", ...},
            "groups": {
                "stefan": {
                    "representative": "Štefánikova",
                    "total_length": 145916.9,
                    "segment_count": 523,
                    "variants": ["Štefánikova", "M. R. Štefánika", ...]
                },
                ...
            }
        }
    """
    mapping = {}
    groups = {}

    for name, length, segments in street_data:
        canonical = normalize_fn(name)
        if not canonical:
            continue

        mapping[name] = canonical

        if canonical not in groups:
            groups[canonical] = {
                "representative": None,
                "total_length": 0.0,
                "segment_count": 0,
                "variants": [],
                "_max_length": 0.0,  # internal, for picking representative
            }

        g = groups[canonical]
        g["total_length"] += length
        g["segment_count"] += segments
        g["variants"].append(name)

        # Representative = variant with highest total length
        if length > g["_max_length"]:
            g["_max_length"] = length
            g["representative"] = name

    # Clean up internal fields and round lengths
    for g in groups.values():
        del g["_max_length"]
        g["total_length"] = round(g["total_length"], 1)

    return {"mapping": mapping, "groups": groups}


def main():
    parser = argparse.ArgumentParser(description="Export normalization mappings as JSON")
    parser.add_argument("--input", "-i", default=COMPUTE_OUTPUT_DEFAULT,
                        help=f"Input CSV from compute.py (default: {COMPUTE_OUTPUT_DEFAULT})")
    parser.add_argument("--out", "-o", default="mappings.json",
                        help="Output JSON path (default: mappings.json)")
    args = parser.parse_args()

    print(f"Loading street names from {args.input}...")
    street_data = load_street_names(args.input)
    print(f"Loaded {len(street_data)} unique street names")

    result = {}
    for method_name, normalize_fn in METHODS:
        print(f"Running method: {method_name}...")
        result[method_name] = build_method_data(normalize_fn, street_data)
        n_groups = len(result[method_name]["groups"])
        print(f"  {len(result[method_name]['mapping'])} names → {n_groups} groups")

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\nMappings written to {args.out}")


if __name__ == "__main__":
    main()
