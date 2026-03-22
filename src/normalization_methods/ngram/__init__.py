#!/usr/bin/env python3
"""
N-gram Jaccard similarity normalization method.
"""

from src.text_utils import preprocess_name

N = 2
THRESHOLD = 0.50

_groups: dict[str, str] = {}
_group_ngrams: dict[str, frozenset] = {}
_mapping: dict[str, str] = {}


def generate_ngrams(text: str, n: int = N) -> frozenset[str]:
    """
    Generate character n-grams from a preprocessed name.

    N-grams are generated per token (word), then combined into a single set.
    Tokens shorter than n are included as-is.
    """
    ngrams: set[str] = set()
    for token in text.split():
        if len(token) < n:
            ngrams.add(token)
        else:
            for i in range(len(token) - n + 1):
                ngrams.add(token[i:i + n])
    return frozenset(ngrams)


def jaccard(a: frozenset, b: frozenset) -> float:
    """Jaccard similarity: |A ∩ B| / |A ∪ B|."""
    if not a or not b:
        return 0.0
    intersection = len(a & b)
    union = len(a | b)
    return intersection / union


def normalize_ngram(name: str) -> str:
    """
    Normalize a street name using N-gram Jaccard clustering.

    Preprocesses the name, generates character n-grams, then compares the
    n-gram set to existing group representatives using Jaccard similarity.
    If the best match is >= THRESHOLD, the name joins that group.
    Otherwise, a new group is created.
    """
    if name in _mapping:
        return _mapping[name]

    preprocessed = preprocess_name(name)
    if not preprocessed:
        return ""

    name_ngrams = generate_ngrams(preprocessed)

    best_match = None
    best_score = 0.0
    for rep, rep_ngrams in _group_ngrams.items():
        score = jaccard(name_ngrams, rep_ngrams)
        if score > best_score:
            best_score = score
            best_match = rep

    if best_match and best_score >= THRESHOLD:
        group_id = _groups[best_match]
    else:
        group_id = preprocessed
        _groups[preprocessed] = group_id
        _group_ngrams[preprocessed] = name_ngrams

    _mapping[name] = group_id
    return group_id
