#!/usr/bin/env python3
"""
Suffix stripping normalization method.

Rule-based deterministic method for Slovak street names. Strips morphological
suffixes (-ová, -ovo, -ského, etc.), removes street types and initials,
and uses the stem of the last significant token as the group key.
"""

import re
from src.text_utils import ascii_norm, INITIAL, STREET_TYPES

ORDINAL = re.compile(r"^\d+[\.\-]?$")

SUFFIXES = ["ovska", "ovske", "ovskeho", "ovskej", "ov", "ova", "ovo", "sky", "ska", "ske", "ski", "eho", "ej", "a",
            "o", "u", "y", "i"]
SUFFIXES = sorted(set(SUFFIXES), key=lambda x: -len(x))


def strip_suffix(token: str) -> str:
    for suf in SUFFIXES:
        if token.endswith(suf) and len(token) - len(suf) >= 3:
            return token[: -len(suf)]
    return token


def normalize_key_suffix_stripping(name: str) -> str:
    s = ascii_norm(name)
    tokens = s.split()
    if not tokens:
        return ""

    for i in range(len(tokens) - 1):
        if ORDINAL.match(tokens[i]):
            nxt = tokens[i + 1]
            if nxt not in STREET_TYPES and not INITIAL.match(nxt) and len(nxt) >= 2:
                number = re.sub(r"\D", "", tokens[i])
                return f"{number}_{nxt}"

    tokens = [t for t in tokens if t not in STREET_TYPES]
    if not tokens:
        return ""

    tokens = [t for t in tokens if not INITIAL.match(t)]
    if not tokens:
        return ""

    last = tokens[-1]
    stem = strip_suffix(last)
    return stem
