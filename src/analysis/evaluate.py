#!/usr/bin/env python3
"""
Evaluate street name normalization methods against Wikidata ground truth.

Metrics:
- Grouping Rate: % of variants per entity that share the dominant normalized group
- Collision Rate: % of normalized groups that contain multiple Wikidata entities
"""

import argparse
import csv
import json
from collections import Counter, defaultdict
from typing import Callable

from src.config import PROBLEM_ENTITIES_TOP_N, COLLISIONS_DISPLAY_N, \
    GROUND_TRUTH_GROUPED_CSV, EVALUATION_OUTPUT_DEFAULT
from src.normalization_methods import NORMALIZATION_METHODS, get_method, method_ids


def load_ground_truth(path: str) -> list[tuple[str, str, list[str]]]:
    """Load ground truth from CSV."""
    entries = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            wikidata_id = row["wikidata_id"]
            entity_label = row["entity_label"]
            variants = [v.strip() for v in row["street_names"].split(";")]
            entries.append((wikidata_id, entity_label, variants))
    return entries


def evaluate(normalize_fn: Callable[[str], str], ground_truth: list[tuple[str, str, list[str]]]) -> dict:
    """
    Evaluate a normalization function against ground truth.

    Args:
        normalize_fn: Function that takes a street name and returns a normalized group ID
        ground_truth: List of (wikidata_id, entity_label, [variants])

    Returns:
        Dict with grouping_rate, collision_rate, and details
    """
    all_normalizations = []
    entity_scores = []

    for wikidata_id, entity_label, variants in ground_truth:
        group_ids = []
        for name in variants:
            group_id = normalize_fn(name)
            group_ids.append(group_id)
            all_normalizations.append((name, wikidata_id, group_id))

        if group_ids:
            counter = Counter(group_ids)
            dominant_count = counter.most_common(1)[0][1]
            entity_score = dominant_count / len(group_ids)
            entity_scores.append({
                "wikidata_id": wikidata_id,
                "entity_label": entity_label,
                "score": entity_score,
                "total_variants": len(group_ids),
                "dominant_count": dominant_count,
                "unique_groups": len(counter)
            })

    grouping_rate = sum(e["score"] for e in entity_scores) / len(entity_scores) if entity_scores else 0.0
    group_to_entities = defaultdict(set)
    for name, wikidata_id, group_id in all_normalizations:
        group_to_entities[group_id].add(wikidata_id)

    total_groups = len(group_to_entities)
    colliding_groups = sum(1 for entities in group_to_entities.values() if len(entities) > 1)
    collision_rate = colliding_groups / total_groups if total_groups > 0 else 0.0
    collisions = []
    for group_id, entity_ids in group_to_entities.items():
        if len(entity_ids) > 1:
            labels = {}
            for wid, label, _ in ground_truth:
                if wid in entity_ids:
                    labels[wid] = label
            collisions.append({
                "group_id": group_id,
                "entities": labels
            })

    problem_entities = sorted(entity_scores, key=lambda x: x["score"])

    return {
        "grouping_rate": grouping_rate,
        "collision_rate": collision_rate,
        "total_entities": len(entity_scores),
        "total_variants": len(all_normalizations),
        "total_groups": total_groups,
        "colliding_groups": colliding_groups,
        "collisions": collisions,
        "problem_entities": problem_entities
    }


def print_results(method_name: str, results: dict, verbose: bool = False):
    print(f"\n{'='*50}")
    print(f"  {method_name}")
    print(f"{'='*50}")
    print(f"Grouping Rate:  {results['grouping_rate']:.1%}")
    print(f"Collision Rate: {results['collision_rate']:.1%}")
    print(f"\nEntities: {results['total_entities']} | "
          f"Variants: {results['total_variants']} | "
          f"Groups: {results['total_groups']}")

    if verbose:
        print(f"\n--- Problem Entities (lowest grouping) ---")
        for e in results["problem_entities"][:PROBLEM_ENTITIES_TOP_N]:
            if e["score"] < 1.0:
                print(f"  {e['entity_label']}: {e['score']:.0%} "
                      f"({e['dominant_count']}/{e['total_variants']} variants, "
                      f"{e['unique_groups']} groups)")

        print(f"\n--- Collisions ({results['colliding_groups']} groups) ---")
        for c in results["collisions"][:COLLISIONS_DISPLAY_N]:
            entities_str = ", ".join(f"{label} ({wid})" for wid, label in c["entities"].items())
            print(f"  '{c['group_id']}' merges: {entities_str}")


def prepare_json_results(all_results: dict) -> dict:
    """Prepare evaluation results for JSON export."""
    output = {}
    for method_name, results in all_results.items():
        output[method_name] = {
            "grouping_rate": round(results["grouping_rate"], 4),
            "collision_rate": round(results["collision_rate"], 4),
            "total_entities": results["total_entities"],
            "total_variants": results["total_variants"],
            "total_groups": results["total_groups"],
            "colliding_groups": results["colliding_groups"],
            "collisions": [
                {
                    "group_id": c["group_id"],
                    "entities": [
                        {"wikidata_id": wid, "label": label}
                        for wid, label in c["entities"].items()
                    ]
                }
                for c in results["collisions"]
            ],
            "problem_entities": [
                {
                    "wikidata_id": e["wikidata_id"],
                    "entity_label": e["entity_label"],
                    "score": round(e["score"], 4),
                    "total_variants": e["total_variants"],
                    "dominant_count": e["dominant_count"],
                    "unique_groups": e["unique_groups"],
                }
                for e in results["problem_entities"]
                if e["score"] < 1.0
            ],
        }
    return output


def main():
    parser = argparse.ArgumentParser(description="Evaluate street name normalization methods")
    parser.add_argument("ground_truth", nargs="?", default=GROUND_TRUTH_GROUPED_CSV,
                        help="Path to ground truth CSV")
    parser.add_argument("-m", "--method", metavar="ID",
                        help=f"Evaluate only this method (choices: {', '.join(method_ids())})")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Show detailed breakdown of problems")
    parser.add_argument("--json", metavar="PATH", default=EVALUATION_OUTPUT_DEFAULT,
                        help="Export results as JSON to this path")
    args = parser.parse_args()

    if args.method:
        entry = get_method(args.method)
        if entry is None:
            parser.error(f"Unknown method '{args.method}'. Available: {', '.join(method_ids())}")
        methods_to_run = [entry]
    else:
        methods_to_run = NORMALIZATION_METHODS

    print(f"Loading ground truth from {args.ground_truth}...")
    ground_truth = load_ground_truth(args.ground_truth)
    print(f"Loaded {len(ground_truth)} entities with multiple variants")

    all_results = {}
    for method_name, normalize_fn in methods_to_run:
        results = evaluate(normalize_fn, ground_truth)
        all_results[method_name] = results
        print_results(method_name, results, verbose=args.verbose)

    if args.json:
        json_data = prepare_json_results(all_results)
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2)
        print(f"\nEvaluation JSON written to {args.json}")


if __name__ == "__main__":
    main()
