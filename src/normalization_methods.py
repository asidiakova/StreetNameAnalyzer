#!/usr/bin/env python3

from typing import Callable
from suffix_stripping import normalize_key_suffix_stripping
from levenshtein_method import normalize_levenshtein
from ngram_method import normalize_ngram
from llm_method import create_llm_normalizer

NORMALIZATION_METHODS: list[tuple[str, Callable[[str], str]]] = [
    ("suffix_stripping", normalize_key_suffix_stripping),
    ("levenshtein", normalize_levenshtein),
    ("ngram", normalize_ngram),
    ("llm_gpt4o_mini", create_llm_normalizer("openai", "gpt-4o-mini")),
    ("llm_claude_haiku", create_llm_normalizer("anthropic", "claude-haiku-4-5-20251001")),
    ("llm_gemini_flash", create_llm_normalizer("gemini", "gemini-2.5-flash")),
]


def get_method(method_id: str) -> tuple[str, Callable[[str], str]] | None:
    for mid, fn in NORMALIZATION_METHODS:
        if mid == method_id:
            return mid, fn
    return None


def method_ids() -> list[str]:
    return [mid for mid, _ in NORMALIZATION_METHODS]
