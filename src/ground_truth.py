#!/usr/bin/env python3
"""
Extract etymology-tagged streets from OSM and validate against Wikidata.
Produces a ground truth dataset for evaluating street name normalization methods.
"""

from __future__ import annotations
import argparse
import csv
import json
import os
import re
import sys
import time
import unicodedata
import psycopg2
import requests
from dotenv import load_dotenv
from unidecode import unidecode
from collections import defaultdict

load_dotenv()

TABLE = "planet_osm_line"
WIKIDATA_CACHE_FILE = "wikidata_cache.json"
REQUEST_DELAY = 0.1  


def parse_args():
    p = argparse.ArgumentParser(description="Generate ground truth from OSM etymology tags + Wikidata validation")
    p.add_argument("--db", "-d", default=os.getenv("DATABASE_URL"), help="Postgres connection URI")
    p.add_argument("--out", "-o", default="ground_truth.csv", help="Output CSV path")
    p.add_argument("--cache", default=WIKIDATA_CACHE_FILE, help="Wikidata metadata cache file")
    p.add_argument("--no-fetch", action="store_true", help="Skip Wikidata API calls, use cache only")
    p.add_argument("--epsg", type=int, default=4326, help="EPSG for length calculation")
    return p.parse_args()


def ascii_normalize(s: str) -> str:
    s = unicodedata.normalize("NFC", s)
    s = unidecode(s)
    s = re.sub(r"[^a-z0-9\s]", " ", s.lower())
    s = re.sub(r"\s+", " ", s).strip()
    return s


def extract_surname(full_name: str) -> str:
    """Extract likely surname from a full name (usually last word)."""
    parts = full_name.strip().split()
    if not parts:
        return ""
    # Handle "Jr.", "II", etc. at the end
    while len(parts) > 1 and (parts[-1] in ("Jr.", "Sr.", "II", "III", "IV") or len(parts[-1]) <= 2):
        parts.pop()
    return parts[-1] if parts else ""


def extract_name_parts(full_name: str) -> list[str]:
    """Extract all significant name parts (for matching first names too)."""
    parts = full_name.strip().split()
    # Filter out short words, prepositions, articles
    skip = {"a", "and", "und", "von", "van", "de", "the", "pri", "nad", "pod", "na", "v"}
    return [p for p in parts if len(p) >= 3 and p.lower() not in skip]


def extract_place_core(place_name: str) -> str:
    """Extract core place name from complex names like 'Vranov nad Topľou'."""
    parts = place_name.strip().split()
    if not parts:
        return ""
    # Usually the first word is the core place name
    return parts[0]


def stem_slovak(word: str) -> str:
    """Simple Slovak suffix stripping for matching."""
    word = ascii_normalize(word)
    suffixes = ["oveho", "ovej", "ova", "ovo", "ov", "eho", "ej", "a", "o", "u", "y", "i", "e"]
    for suf in suffixes:
        if word.endswith(suf) and len(word) - len(suf) >= 3:
            return word[:-len(suf)]
    return word


def compute_match_confidence(street_name: str, entity_labels: list[str], entity_type: str) -> float:
    """
    Compute confidence that street_name is actually named after the entity.
    Returns 1.0 for high confidence, 0.5 for partial, 0.0 for no match.
    """
    street_norm = ascii_normalize(street_name)
    street_stem = stem_slovak(street_name)
    
    for label in entity_labels:
        label_norm = ascii_normalize(label)
        
        # Direct containment (highest confidence)
        if label_norm in street_norm or street_norm in label_norm:
            return 1.0
        
        # For places: extract core place name and match
        if entity_type == "place":
            place_core = extract_place_core(label)
            if place_core:
                place_norm = ascii_normalize(place_core)
                place_stem = stem_slovak(place_core)
                
                if place_norm in street_norm:
                    return 1.0
                if len(place_stem) >= 3 and place_stem in street_stem:
                    return 0.9
        
        # For humans: check all name parts (not just surname)
        name_parts = extract_name_parts(label)
        for part in name_parts:
            part_norm = ascii_normalize(part)
            part_stem = stem_slovak(part)
            
            if part_norm in street_norm:
                return 1.0
            
            if len(part_stem) >= 3 and part_stem in street_stem:
                return 0.9
            
            if len(part_stem) >= 4 and street_stem.startswith(part_stem[:4]):
                return 0.7
    
    return 0.0


def fetch_wikidata_entity(qid: str) -> dict | None:
    """Fetch entity metadata from Wikidata API."""
    url = f"https://www.wikidata.org/wiki/Special:EntityData/{qid}.json"
    headers = {
        "User-Agent": "StreetNameAnalyzer/1.0 (academic research project; contact: your@email.com)"
    }
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        entity = data.get("entities", {}).get(qid, {})
        
        labels = []
        for lang in ["sk", "cs", "en", "de", "hu"]:
            if lang in entity.get("labels", {}):
                labels.append(entity["labels"][lang]["value"])
            for alias in entity.get("aliases", {}).get(lang, []):
                labels.append(alias["value"])
        
        # Get entity type (instance of - P31)
        instance_of = []
        for claim in entity.get("claims", {}).get("P31", []):
            try:
                instance_of.append(claim["mainsnak"]["datavalue"]["value"]["id"])
            except (KeyError, TypeError):
                pass
        
        # Check if human (Q5)
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


def extract_etymology_data(conn, epsg: int) -> list[dict]:
    """Extract all streets with etymology tags from the database."""
    cur = conn.cursor()
    
    length_expr = f"ST_Length(ST_Transform(way, {epsg})::geography)" if epsg == 4326 else f"ST_Length(ST_Transform(way, {epsg}))"
    
    sql = f"""
        SELECT 
            name,
            tags->'name:etymology:wikidata' AS wikidata_id,
            SUM({length_expr}) AS total_length,
            COUNT(*) AS segments
        FROM {TABLE}
        WHERE name IS NOT NULL 
          AND highway IS NOT NULL
          AND tags->'name:etymology:wikidata' IS NOT NULL
        GROUP BY name, tags->'name:etymology:wikidata'
        ORDER BY total_length DESC
    """
    
    cur.execute(sql)
    rows = cur.fetchall()
    
    return [
        {"name": row[0], "wikidata_id": row[1], "total_length": row[2], "segments": row[3]}
        for row in rows
    ]


def main():
    args = parse_args()
    
    if not args.db:
        print("Error: provide --db or set DATABASE_URL env var.", file=sys.stderr)
        sys.exit(1)
    

    conn = psycopg2.connect(args.db)
    try:
        print("Extracting etymology-tagged streets...")
        raw_data = extract_etymology_data(conn, args.epsg)
        print(f"Found {len(raw_data)} street-entity pairs")
    finally:
        conn.close()
    

    unique_qids = set(row["wikidata_id"] for row in raw_data if row["wikidata_id"])
    print(f"Unique Wikidata entities: {len(unique_qids)}")
    

    cache = load_wikidata_cache(args.cache)
    
    if not args.no_fetch:
        missing = [qid for qid in unique_qids if qid not in cache]
        if missing:
            for i, qid in enumerate(missing):
                if (i + 1) % 10 == 0:
                    print(f"  {i + 1}/{len(missing)}...")
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
            tier = "gold" if confidence >= 0.7 else "silver" if confidence >= 0.5 else "excluded"
            primary_label = entity["primary_label"]
            is_human = entity["is_human"]
        else:
            confidence = 0.0
            tier = "unknown"
            primary_label = qid
            is_human = None
        
        results.append({
            "street_name": row["name"],
            "wikidata_id": qid,
            "entity_label": primary_label,
            "is_human": is_human,
            "confidence": confidence,
            "tier": tier,
            "total_length": row["total_length"],
            "segments": row["segments"]
        })
    

    with open(args.out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "street_name", "wikidata_id", "entity_label", "is_human", 
            "confidence", "tier", "total_length", "segments"
        ])
        writer.writeheader()
        writer.writerows(results)
    

    tiers = {}
    for r in results:
        tiers[r["tier"]] = tiers.get(r["tier"], 0) + 1
    
    print(f"\nResults written to {args.out}")
    print(f"Tier breakdown:")
    for tier, count in sorted(tiers.items()):
        print(f"  {tier}: {count}")
    

    grouped_out = args.out.replace(".csv", "_grouped.csv")

    groups = defaultdict(list)
    for r in results:
        if r["tier"] in ("gold", "silver"):
            groups[r["wikidata_id"]].append(r)
    

    multi_variant_groups = {k: v for k, v in groups.items() if len(v) > 1}
    
    with open(grouped_out, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["wikidata_id", "entity_label", "is_human", "variant_count", "street_names", "total_length"])
        
        for qid, entries in sorted(multi_variant_groups.items(), key=lambda x: -sum(e["total_length"] for e in x[1])):
            names = "; ".join(sorted(set(e["street_name"] for e in entries)))
            total_len = sum(e["total_length"] for e in entries)
            entity_label = entries[0]["entity_label"]
            is_human = entries[0]["is_human"]
            writer.writerow([qid, entity_label, is_human, len(entries), names, f"{total_len:.1f}"])
    
    print(f"\nGrouped ground truth (multi-variant entities): {grouped_out}")
    print(f"  Entities with multiple name variants: {len(multi_variant_groups)}")


if __name__ == "__main__":
    main()
