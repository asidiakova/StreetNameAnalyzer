#!/usr/bin/env python3
"""
Levenshtein distance-based street name normalization.

Uses greedy clustering: for each new name, compare it to existing group
representatives. If similar enough (above threshold), join that group.
Otherwise, start a new group.

This is a fundamentally different approach from suffix stripping:
- Suffix stripping is rule-based (strips known suffixes)
- Levenshtein is similarity-based (compares character-by-character)

Note: This method is stateful — it builds groups incrementally as names
are processed. The module-level state resets naturally between script runs.
"""

from rapidfuzz import fuzz
from text_utils import ascii_norm, INITIAL, STREET_TYPES

# Similarity threshold (0-100). Higher = stricter (fewer merges, more groups).
THRESHOLD = 80

# Module-level state for greedy clustering
_groups: dict[str, str] = {}    # preprocessed representative → group_id
_mapping: dict[str, str] = {}   # original name → group_id


def preprocess(name: str) -> str:
    """
    Preprocess a street name before Levenshtein comparison.
    Same base preprocessing as suffix stripping (ASCII normalize, remove
    street types, remove initials), but keeps all remaining tokens
    instead of just the last one.
    """
    s = ascii_norm(name)

    tokens = s.split()
    if not tokens:
        return ""

    # Remove street type tokens
    tokens = [t for t in tokens if t not in STREET_TYPES]
    if not tokens:
        return ""

    # Remove single-letter initials (e.g., "m", "r", "j")
    tokens = [t for t in tokens if not INITIAL.match(t)]
    if not tokens:
        return ""

    return " ".join(tokens)


def normalize_levenshtein(name: str) -> str:
    """
    Normalize a street name using greedy Levenshtein clustering.

    Preprocesses the name, then compares it to all existing group
    representatives using character similarity (rapidfuzz.fuzz.ratio).
    If the best match is >= THRESHOLD, the name joins that group.
    Otherwise, a new group is created.
    """
    # Return cached result if already seen
    if name in _mapping:
        return _mapping[name]

    preprocessed = preprocess(name)
    if not preprocessed:
        return ""

    # Find best match among existing group representatives
    best_match = None
    best_score = 0
    for representative in _groups:
        score = fuzz.ratio(preprocessed, representative)
        if score > best_score:
            best_score = score
            best_match = representative

    if best_match and best_score >= THRESHOLD:
        # Similar enough — join existing group
        group_id = _groups[best_match]
    else:
        # Not similar enough — create new group
        # Use the preprocessed name as group_id (readable in output)
        group_id = preprocessed
        _groups[preprocessed] = group_id

    _mapping[name] = group_id
    return group_id
