#!/usr/bin/env python3
"""
Suffix stripping normalization method.

Rule-based deterministic method for Slovak street names. Strips morphological
suffixes (-ová, -ovo, -ského, etc.), removes street types and initials,
and uses the stem of the last significant token as the group key.

Known limitations documented below — these are intentional for method comparison.
"""
import re
from text_utils import ascii_norm, INITIAL, STREET_TYPES

#   CURRENT PROBLEMS:
#   1. Over-merges different people with same surname:
#   e.g., Janka Kráľa + Fraňa Kráľa + Kráľovská cesta → all become "kral"
#   2. Over-merges different groups/concepts sharing a common noun root:
#   e.g., Československej armády + Červenej armády + Sovietskej armády → "armad"
#   3. Over-merges unrelated places with common noun roots:
#   e.g., Červená hora + Stará hora + Pavla Horova → "hora"
#   4. Groups everything ending with Roman numerals together:
#   e.g., Zelená voda II. + Jána Pavla II. + Sídlisko II → "II"

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

    # detect ordinals = dates like  1. maja, 9. maja,  etc.
    for i in range(len(tokens) - 1):
        if ORDINAL.match(tokens[i]):
            nxt = tokens[i + 1]
            # skip if next token is a street-type or an initial or too short
            if nxt not in STREET_TYPES and not INITIAL.match(nxt) and len(nxt) >= 2:
                # normalize ordinal to digits only (strip '.' or '-')
                number = re.sub(r"\D", "", tokens[i])
                return f"{number}_{nxt}"

    # preserve ordinals/numeric-prefixed streets that start the name (keep prior behavior)
    if ORDINAL.match(tokens[0]) or tokens[0].isdigit():
        return "_".join(tokens)

    # remove street-type tokens
    tokens = [t for t in tokens if t not in STREET_TYPES]
    if not tokens:
        return ""

    # remove single-letter initials (and single letters with dot already removed by ascii_norm)
    tokens = [t for t in tokens if not INITIAL.match(t)]
    if not tokens:
        return ""

    last = tokens[-1]
    stem = strip_suffix(last)
    return stem


