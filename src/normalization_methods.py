#!/usr/bin/env python3

from typing import Callable
from normalize import normalize_key

NORMALIZATION_METHODS: list[tuple[str, Callable[[str], str]]] = [
    ("suffix_stripping", normalize_key),
]


def get_method(method_id: str) -> tuple[str, Callable[[str], str]] | None:
    for mid, fn in NORMALIZATION_METHODS:
        if mid == method_id:
            return mid, fn
    return None


def method_ids() -> list[str]:
    return [mid for mid, _ in NORMALIZATION_METHODS]
