#!/usr/bin/env python3

from typing import Callable
from suffix_stripping import normalize_key_suffix_stripping
from levenshtein_method import normalize_levenshtein
from ngram_method import normalize_ngram
from embedding_method import create_embedding_normalizer

NORMALIZATION_METHODS: list[tuple[str, Callable[[str], str]]] = [
    ("suffix_stripping", normalize_key_suffix_stripping),
    ("levenshtein", normalize_levenshtein),
    ("ngram", normalize_ngram),
    ("embedding_minilm", create_embedding_normalizer(
        "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        threshold=0.80,
    )),
    ("embedding_mpnet", create_embedding_normalizer(
        "sentence-transformers/paraphrase-multilingual-mpnet-base-v2",
        threshold=0.80,
    )),
]


def get_method(method_id: str) -> tuple[str, Callable[[str], str]] | None:
    for mid, fn in NORMALIZATION_METHODS:
        if mid == method_id:
            return mid, fn
    return None


def method_ids() -> list[str]:
    return [mid for mid, _ in NORMALIZATION_METHODS]
