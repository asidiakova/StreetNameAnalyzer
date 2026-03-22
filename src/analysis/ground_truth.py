#!/usr/bin/env python3

import argparse
import csv
import json
import os
import sys
import time
import psycopg2
import requests
from collections import defaultdict


from src.config import (
    REQUEST_DELAY,
    WIKIDATA_TIMEOUT,
    WIKIDATA_LABEL_LANGUAGES,
    CONFIDENCE_THRESHOLD,
    CONFIDENCE_EXACT,
    CONFIDENCE_STEM,
    CONFIDENCE_PREFIX,
    GROUND_TRUTH_CSV,
)

from src.text_utils import ascii_norm

_MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
_DEFAULT_WIKIDATA_CACHE = os.path.join(_MODULE_DIR, "wikidata_cache.json")


def extract_name_parts(full_name: str) -> list[str]:
    parts = full_name.strip().split()
    return [p for p in parts if len(p) >= 3]


def extract_place_core(place_name: str) -> str:
    parts = place_name.strip().split()
    if not parts:
        return ""
    return parts[0]


def stem_slovak(word: str) -> str:
    word = ascii_norm(word)
    suffixes = ["oveho", "ovej", "ova", "ovo", "ov", "eho", "ej", "a", "o", "u", "y", "i", "e"]
    for suf in suffixes:
        if word.endswith(suf) and len(word) - len(suf) >= 3:
            return word[:-len(suf)]
    return word


def compute_match_confidence(street_name: str, entity_labels: list[str], entity_type: str) -> float:
    street_norm = ascii_norm(street_name)
    street_stem = stem_slovak(street_name)

    for label in entity_labels:
        label_norm = ascii_norm(label)

        if label_norm in street_norm or street_norm in label_norm:
            return CONFIDENCE_EXACT

        if entity_type == "place":
            place_core = extract_place_core(label)
            if place_core:
                place_norm = ascii_norm(place_core)
                place_stem = stem_slovak(place_core)
                if place_norm in street_norm:
                    return CONFIDENCE_EXACT
                if len(place_stem) >= 3 and place_stem in street_stem:
                    return CONFIDENCE_STEM

        name_parts = extract_name_parts(label)
        for part in name_parts:
            part_norm = ascii_norm(part)
            part_stem = stem_slovak(part)
            if part_norm in street_norm:
                return CONFIDENCE_EXACT
            if len(part_stem) >= 3 and part_stem in street_stem:
                return CONFIDENCE_STEM
            if len(part_stem) >= 4 and street_stem.startswith(part_stem[:4]):
                return CONFIDENCE_PREFIX

    return 0.0


def fetch_wikidata_entity(qid: str) -> dict | None:
    url = f"https://www.wikidata.org/wiki/Special:EntityData/{qid}.json"
    headers = {
        "User-Agent": "StreetNameAnalyzer"
    }
    try:
        print(f"Fetching data for entity {qid}")
        resp = requests.get(url, headers=headers, timeout=WIKIDATA_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        entity = data.get("entities", {}).get(qid, {})

        labels = []
        for lang in WIKIDATA_LABEL_LANGUAGES:
            if lang in entity.get("labels", {}):
                labels.append(entity["labels"][lang]["value"])
            for alias in entity.get("aliases", {}).get(lang, []):
                labels.append(alias["value"])

        instance_of = []
        for claim in entity.get("claims", {}).get("P31", []):
            try:
                instance_of.append(claim["mainsnak"]["datavalue"]["value"]["id"])
            except (KeyError, TypeError):
                pass

        is_human = "Q5" in instance_of

        return {
            "qid": qid,
            "labels": list(set(labels)),
            "instance_of": instance_of,
            "is_human": is_human,
            "primary_label": labels[0] if labels else qid
        }
    except Exception as e:
        print(f"Warning: Failed to fetch {qid}: {e}", file=sys.stderr)
        return None


def load_wikidata_cache(path: str) -> dict:
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_wikidata_cache(cache: dict, path: str):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def extract_etymology_data(conn) -> list[dict]:
    cur = conn.cursor()

    sql = f"""
        SELECT DISTINCT
            name,
            tags->'name:etymology:wikidata' AS wikidata_id
        FROM planet_osm_line
        WHERE name IS NOT NULL
          AND highway IS NOT NULL
          AND tags->'name:etymology:wikidata' IS NOT NULL
        ORDER BY name
    """

    cur.execute(sql)
    rows = cur.fetchall()

    return [{"name": row[0], "wikidata_id": row[1]} for row in rows]


def main():
    parser = argparse.ArgumentParser(description="Generate ground truth from OSM etymology tags + Wikidata validation")
    parser.add_argument("--out", "-o", default=GROUND_TRUTH_CSV, help="Output CSV path")
    parser.add_argument("--cache", default=_DEFAULT_WIKIDATA_CACHE, help="Wikidata metadata cache file")
    args = parser.parse_args()

    db_conn_str = os.getenv("DATABASE_URL")
    conn = psycopg2.connect(db_conn_str)
    try:
        print("Extracting etymology-tagged streets...")
        raw_data = extract_etymology_data(conn)
        print(f"Found {len(raw_data)} street-entity pairs")
    finally:
        conn.close()

    unique_qids = set(row["wikidata_id"] for row in raw_data if row["wikidata_id"])
    print(f"Unique Wikidata entities: {len(unique_qids)}")

    cache = load_wikidata_cache(args.cache)

    missing = [qid for qid in unique_qids if qid not in cache]
    if missing:
        for _, qid in enumerate(missing):
            entity = fetch_wikidata_entity(qid)
            if entity:
                cache[qid] = entity
            time.sleep(REQUEST_DELAY)
        save_wikidata_cache(cache, args.cache)

    results = []
    for row in raw_data:
        qid = row["wikidata_id"]
        entity = cache.get(qid)

        if entity:
            entity_type = "human" if entity["is_human"] else "place"
            confidence = compute_match_confidence(row["name"], entity["labels"], entity_type)
            primary_label = entity["primary_label"]
            is_human = entity["is_human"]
        else:
            confidence = 0.0
            primary_label = qid
            is_human = None

        results.append({
            "street_name": row["name"],
            "wikidata_id": qid,
            "entity_label": primary_label,
            "is_human": is_human,
            "confidence": confidence
        })

    with open(args.out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "street_name", "wikidata_id", "entity_label", "is_human", "confidence"
        ])
        writer.writeheader()
        writer.writerows(results)

    valid_count = sum(1 for r in results if r["confidence"] >= CONFIDENCE_THRESHOLD)
    excluded_count = len(results) - valid_count

    print(f"\nResults written to {args.out}")
    print(f"Confidence breakdown:")
    print(f"  Valid (>={CONFIDENCE_THRESHOLD}): {valid_count}")
    print(f"  Excluded (<{CONFIDENCE_THRESHOLD}): {excluded_count}")

    grouped_out = args.out.replace(".csv", "_grouped.csv")

    groups = defaultdict(list)
    for r in results:
        if r["confidence"] >= CONFIDENCE_THRESHOLD:
            groups[r["wikidata_id"]].append(r)

    multi_variant_groups = {k: v for k, v in groups.items() if len(v) > 1}

    with open(grouped_out, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["wikidata_id", "entity_label", "is_human", "street_names"])

        for qid, entries in sorted(multi_variant_groups.items(), key=lambda x: x[0]):
            names = "; ".join(sorted(set(e["street_name"] for e in entries)))
            entity_label = entries[0]["entity_label"]
            is_human = entries[0]["is_human"]
            writer.writerow([qid, entity_label, is_human, names])

    print(f"\nGrouped ground truth (multi-variant entities): {grouped_out}")
    print(f"  Entities with multiple name variants: {len(multi_variant_groups)}")


if __name__ == "__main__":
    main()
