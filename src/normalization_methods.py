#!/usr/bin/env python3

from typing import Callable
from suffix_stripping import normalize_key_suffix_stripping
from levenshtein_method import normalize_levenshtein

NORMALIZATION_METHODS: list[tuple[str, Callable[[str], str]]] = [
    ("suffix_stripping", normalize_key_suffix_stripping),
    ("levenshtein", normalize_levenshtein),
]


def get_method(method_id: str) -> tuple[str, Callable[[str], str]] | None:
    for mid, fn in NORMALIZATION_METHODS:
        if mid == method_id:
            return mid, fn
    return None


def method_ids() -> list[str]:
    return [mid for mid, _ in NORMALIZATION_METHODS]
