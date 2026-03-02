#!/usr/bin/env python3
"""
Shared text preprocessing utilities for street name normalization.
"""

import re
import unicodedata
from unidecode import unidecode

# Replaces anything that isn't a letter, digit, or whitespace with a space.
# Hyphens are not preserved (e.g., "Česko-slovenskej" vs "Česko slovenskej"), so removing them normalizes both forms to the same token sequence.
_NONLETTER = re.compile(r"[^a-z0-9\s]", re.IGNORECASE)

# Matches single-letter initials like "M", "R", "J", "M."
INITIAL = re.compile(r"^[a-z]\.?$", re.IGNORECASE)

# Common Slovak street type tokens (in their ASCII-normalized forms).
# These are removed during preprocessing since they don't help distinguish streets.
STREET_TYPES = {
    "ulica", "ul", "cesta", "namestie", "nam", "trieda",
    "aleja", "park", "sady", "most", "nabr", "nabrezie",
    "chodnik", "plac", "ut", "utca", "dolina",
}


def ascii_norm(s: str) -> str:
    """
    Normalize a string to ASCII lowercase with single-space separation.
    """
    s = unicodedata.normalize("NFC", s)
    s = unidecode(s)
    s = _NONLETTER.sub(" ", s).lower().strip()
    s = re.sub(r"\s+", " ", s)
    return s


def preprocess_name(name: str) -> str:
    """
    Preprocess a street name for similarity-based methods.

    Applies ASCII normalization, removes street type tokens and
    single-letter initials, and returns all remaining tokens joined
    by spaces. Used by Levenshtein, N-gram, and other similarity methods.
    """
    s = ascii_norm(name)

    tokens = s.split()
    if not tokens:
        return ""

    tokens = [t for t in tokens if t not in STREET_TYPES]
    if not tokens:
        return ""

    tokens = [t for t in tokens if not INITIAL.match(t)]
    if not tokens:
        return ""

    return " ".join(tokens)
