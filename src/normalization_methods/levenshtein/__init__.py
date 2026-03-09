#!/usr/bin/env python3
"""
Levenshtein distance-based street name normalization.
"""

from rapidfuzz import fuzz
from src.text_utils import preprocess_name

THRESHOLD = 80

_groups: dict[str, str] = {}
_mapping: dict[str, str] = {}


def normalize_levenshtein(name: str) -> str:
    """
    Normalize a street name using Levenshtein clustering.

    Preprocesses the name, then compares it to all existing group representatives
    using character similarity. If the best match is >= THRESHOLD, the name joins
    that group. Otherwise, a new group is created.
    """
    if name in _mapping:
        return _mapping[name]

    preprocessed = preprocess_name(name)
    if not preprocessed:
        return ""

    best_match = None
    best_score = 0
    for representative in _groups:
        score = fuzz.ratio(preprocessed, representative)
        if score > best_score:
            best_score = score
            best_match = representative

    if best_match and best_score >= THRESHOLD:
        group_id = _groups[best_match]
    else:
        group_id = preprocessed
        _groups[preprocessed] = group_id

    _mapping[name] = group_id
    return group_id
