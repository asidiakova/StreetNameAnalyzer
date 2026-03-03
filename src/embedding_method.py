#!/usr/bin/env python3
"""
Sentence transformer embedding-based normalization using greedy clustering.

Uses multilingual sentence transformers to encode street names as dense vectors,
then clusters them by cosine similarity. Supports multiple models via a factory
function — each call creates an independent normalizer with its own state.

See docs/embedding.md for detailed description, examples, and known limitations.
"""

import numpy as np
from text_utils import ascii_norm, preprocess_name, INITIAL, STREET_TYPES
from sentence_transformers import SentenceTransformer

# Default cosine similarity threshold (0.0–1.0).
# Embeddings are L2-normalized, so cosine similarity = dot product.
DEFAULT_THRESHOLD = 0.70


def preprocess_for_embedding(name: str) -> str:
    """
    Preprocess a street name for transformer encoding, keeping original diacritics.

    Removes street types and single-letter initials (same filtering as
    preprocess_name), but preserves the original characters so the
    multilingual model can leverage its training on accented text.
    """
    tokens = name.strip().split()
    result = []
    for token in tokens:
        ascii_token = ascii_norm(token)
        if ascii_token in STREET_TYPES:
            continue
        if INITIAL.match(ascii_token):
            continue
        if not ascii_token:
            continue
        result.append(token)
    return " ".join(result).strip()


def create_embedding_normalizer(model_name: str, threshold: float = DEFAULT_THRESHOLD):
    """
    Factory that returns a normalize function for a specific transformer model.

    The model is loaded lazily on the first call, so importing this module
    doesn't trigger a heavy download or GPU allocation. Each returned
    function has its own isolated state (groups, embedding cache, mapping).

    Args:
        model_name: Hugging Face model identifier
            (e.g. "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
        threshold: Minimum cosine similarity to merge into an existing group
    """
    _state = {
        "model": None,
        "groups": {},            # emb_input → group_id (ASCII-normalized)
        "group_embeddings": {},  # emb_input → numpy array (unit-length)
        "mapping": {},           # original name → group_id
    }

    def normalize(name: str) -> str:
        if name in _state["mapping"]:
            return _state["mapping"][name]

        # Lazy model loading
        if _state["model"] is None:
            _state["model"] = SentenceTransformer(model_name)

        emb_input = preprocess_for_embedding(name)
        if not emb_input:
            return ""

        # ASCII-based group ID for consistency with other methods
        group_id_candidate = preprocess_name(name) or ascii_norm(emb_input)

        embedding = _state["model"].encode(emb_input, normalize_embeddings=True)

        best_match = None
        best_score = 0.0
        for rep_key, rep_emb in _state["group_embeddings"].items():
            score = float(np.dot(embedding, rep_emb))
            if score > best_score:
                best_score = score
                best_match = rep_key

        if best_match is not None and best_score >= threshold:
            group_id = _state["groups"][best_match]
        else:
            group_id = group_id_candidate
            _state["groups"][emb_input] = group_id
            _state["group_embeddings"][emb_input] = embedding

        _state["mapping"][name] = group_id
        return group_id

    return normalize
