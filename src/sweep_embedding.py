#!/usr/bin/env python3
"""
Threshold sweep for sentence transformer embedding methods.

Encodes all ground truth names once per model, then evaluates multiple
thresholds without re-encoding — much faster than running evaluate.py
repeatedly.
"""

import csv
import numpy as np
from collections import Counter, defaultdict

from config import EVALUATE_GROUND_TRUTH_DEFAULT
from text_utils import ascii_norm, preprocess_name
from embedding_method import preprocess_for_embedding


def load_ground_truth(path: str):
    entries = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            variants = [v.strip() for v in row["street_names"].split(";")]
            entries.append((row["wikidata_id"], row["entity_label"], variants))
    return entries


def encode_all_names(model, ground_truth):
    """Encode every unique name once. Returns dict: original_name → embedding."""
    all_names = []
    for _, _, variants in ground_truth:
        all_names.extend(variants)

    unique_names = list(set(all_names))
    emb_inputs = []
    valid_names = []
    for name in unique_names:
        emb_input = preprocess_for_embedding(name)
        if emb_input:
            emb_inputs.append(emb_input)
            valid_names.append(name)

    print(f"  Encoding {len(emb_inputs)} unique preprocessed names...")
    embeddings = model.encode(emb_inputs, normalize_embeddings=True,
                              show_progress_bar=True, batch_size=64)

    name_to_emb = {}
    for name, emb in zip(valid_names, embeddings):
        name_to_emb[name] = emb
    return name_to_emb


def greedy_cluster(names, name_to_emb, threshold):
    """Run greedy clustering at a given threshold. Returns name → group_id mapping."""
    groups = {}        # emb_input → group_id
    group_embs = {}    # emb_input → embedding
    mapping = {}       # original name → group_id

    for name in names:
        if name in mapping:
            continue

        emb_input = preprocess_for_embedding(name)
        if not emb_input or name not in name_to_emb:
            continue

        embedding = name_to_emb[name]
        group_id_candidate = preprocess_name(name) or ascii_norm(emb_input)

        best_match = None
        best_score = 0.0
        for rep_key, rep_emb in group_embs.items():
            score = float(np.dot(embedding, rep_emb))
            if score > best_score:
                best_score = score
                best_match = rep_key

        if best_match is not None and best_score >= threshold:
            group_id = groups[best_match]
        else:
            group_id = group_id_candidate
            groups[emb_input] = group_id
            group_embs[emb_input] = embedding

        mapping[name] = group_id

    return mapping


def evaluate_at_threshold(ground_truth, name_to_emb, threshold):
    """Evaluate grouping rate and collision rate at a given threshold."""
    all_names = []
    for _, _, variants in ground_truth:
        all_names.extend(variants)

    mapping = greedy_cluster(all_names, name_to_emb, threshold)

    entity_scores = []
    all_normalizations = []

    for wikidata_id, entity_label, variants in ground_truth:
        group_ids = []
        for name in variants:
            gid = mapping.get(name)
            if gid:
                group_ids.append(gid)
                all_normalizations.append((name, wikidata_id, gid))

        if group_ids:
            counter = Counter(group_ids)
            dominant_count = counter.most_common(1)[0][1]
            entity_scores.append(dominant_count / len(group_ids))

    grouping_rate = sum(entity_scores) / len(entity_scores) if entity_scores else 0.0

    group_to_entities = defaultdict(set)
    for name, wid, gid in all_normalizations:
        group_to_entities[gid].add(wid)

    total_groups = len(group_to_entities)
    colliding = sum(1 for ents in group_to_entities.values() if len(ents) > 1)
    collision_rate = colliding / total_groups if total_groups > 0 else 0.0

    return grouping_rate, collision_rate, total_groups


def main():
    gt_path = EVALUATE_GROUND_TRUTH_DEFAULT
    thresholds = [0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85]

    models = [
        ("MiniLM-L12", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"),
        ("MPNet-base", "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"),
    ]

    print(f"Loading ground truth from {gt_path}...")
    ground_truth = load_ground_truth(gt_path)
    print(f"Loaded {len(ground_truth)} entities\n")

    for model_label, model_name in models:
        print(f"=== {model_label} ({model_name}) ===")
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer(model_name)
        name_to_emb = encode_all_names(model, ground_truth)

        print(f"\n  {'Threshold':>10} | {'Grouping':>10} | {'Collision':>10} | {'Groups':>8}")
        print(f"  {'-'*10}-+-{'-'*10}-+-{'-'*10}-+-{'-'*8}")
        for t in thresholds:
            gr, cr, ng = evaluate_at_threshold(ground_truth, name_to_emb, t)
            print(f"  {t:>10.2f} | {gr:>9.1%} | {cr:>9.1%} | {ng:>8}")
        print()

        del model


if __name__ == "__main__":
    main()
