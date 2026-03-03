# Sentence Transformer Embeddings

**File**: `src/embedding_method.py`
**Type**: ML-based (dense vector similarity), stateful
**Language-specific**: No (multilingual models)

## Algorithm

1. **Preprocess** the input name: Remove street types and single-letter initials (same filtering as deterministic methods), but **keep original diacritics** — the multilingual transformer model was trained on accented text and benefits from it
2. **Encode** the preprocessed name into a dense vector (embedding) using a pre-trained sentence transformer
3. **Look up cache**: If this exact name was already processed, return the cached group ID
4. **Compare** the embedding to all existing group representatives using **cosine similarity** (dot product of unit-length vectors)
5. **If best match >= threshold**: Join that group
6. **Otherwise**: Create a new group with this name as the representative

### Key design decisions

- **Diacritics preserved**: Unlike all deterministic methods (which ASCII-normalize to e.g. "stefanikova"), the embedding input keeps the original form ("Štefánikova"). This allows the model to leverage its multilingual training on Slovak text.
- **Lazy model loading**: The transformer model is only loaded on the first call to the normalizer function, not at import time. This avoids slow startup when importing `normalization_methods.py`.
- **Factory pattern**: `create_embedding_normalizer(model_name, threshold)` returns a closure with isolated state. This allows registering multiple models (e.g., MiniLM and MPNet) as independent methods in the same registry.
- **Group IDs use ASCII**: Despite encoding with diacritics, the group ID is still the ASCII-preprocessed form (via `preprocess_name`) for consistency with the deterministic methods.

### Models compared

| Model                                   | Parameters | Embedding dim | Speed (724 names) | Size    |
|-----------------------------------------|------------|---------------|-------------------|---------|
| `paraphrase-multilingual-MiniLM-L12-v2` | 118M       | 384           | ~3 sec            | ~470 MB |
| `paraphrase-multilingual-mpnet-base-v2` | 278M       | 768           | ~12 sec           | ~1.1 GB |

Both are trained on parallel sentence pairs across 50+ languages, including Slovak, Czech, and Hungarian — all relevant for Slovak street names.

## Example

Consider "Štefánikova" and "M. R. Štefánika":
- After preprocessing (remove initials "M.", "R."): → "Štefánikova" and "Štefánika"
- The transformer encodes both into dense vectors that capture the semantic similarity of the root "Štefánik"
- Cosine similarity between the two embeddings: ~0.85–0.95 (high, correctly grouped)

Where it fails — "Štefánikova" vs "Štefanová":
- Both share the "Štefan" root, and the model produces moderately similar embeddings (~0.75)
- If threshold is too low, these get incorrectly merged (they refer to different people)

## Evaluation Results

### Threshold sweep — MiniLM-L12

| Threshold | Grouping Rate | Collision Rate | Groups  |
|-----------|---------------|----------------|---------|
| 0.50      | 90.8%         | 47.8%          | 23      |
| 0.55      | 84.7%         | 40.0%          | 35      |
| 0.60      | 78.6%         | 49.0%          | 51      |
| 0.65      | 76.4%         | 43.9%          | 82      |
| 0.70      | 75.0%         | 42.9%          | 119     |
| 0.75      | 71.1%         | 32.2%          | 177     |
| **0.80**  | **69.7%**     | **26.4%**      | **239** |
| 0.85      | 66.3%         | 17.1%          | 316     |

### Threshold sweep — MPNet-base

| Threshold | Grouping Rate | Collision Rate | Groups  |
|-----------|---------------|----------------|---------|
| 0.50      | 72.0%         | 59.5%          | 42      |
| 0.55      | 71.2%         | 51.7%          | 60      |
| 0.60      | 72.0%         | 54.7%          | 95      |
| 0.65      | 72.1%         | 46.4%          | 125     |
| 0.70      | 74.3%         | 36.3%          | 157     |
| 0.75      | 75.4%         | 30.7%          | 215     |
| **0.80**  | **71.2%**     | **18.9%**      | **286** |
| 0.85      | 65.3%         | 13.4%          | 367     |

**Default threshold**: 0.80 for both models

### Comparison across all methods

| Method                        | Grouping Rate | Collision Rate | Groups  |
|-------------------------------|---------------|----------------|---------|
| Suffix stripping              | 94.7%         | 5.4%           | 240     |
| N-gram (t=0.50)               | 79.9%         | 9.6%           | 311     |
| **Embedding MiniLM (t=0.80)** | **69.7%**     | **26.4%**      | **239** |
| **Embedding MPNet (t=0.80)**  | **71.2%**     | **18.9%**      | **286** |
| Levenshtein (t=80)            | 63.6%         | 7.2%           | 418     |

## Analysis

The embedding methods produce **significantly higher collision rates** than all deterministic methods. This is the key finding: while transformers understand semantic similarity at a deeper level, this becomes a liability for street name normalization.

### Why collisions are high

The transformer models are trained to map semantically similar text to nearby vectors. For street names, this means:
- "Štefánikova" and "Štefanová" are close in embedding space (shared "Štefan" root) even though they refer to different people
- "Križkova" and "Krasková" share enough structural similarity for the model to consider them related
- The model has no concept of "different Wikidata entity" — it only sees text similarity

At threshold 0.80 with MiniLM, the `'krizkova'` group incorrectly merges 10 different entities (Križko, Kostra, Králik, Klempa, Krasko, Jarunková, Krčméry, Krman, Kmeťko, Kmeť) — all names that the model considers structurally similar.

### MiniLM vs MPNet

- **MiniLM** is more aggressive: higher grouping at any threshold, but much higher collision. Its smaller embedding dimension (384 vs 768) means it has less capacity to distinguish fine-grained differences between similar names.
- **MPNet** is more conservative: lower collision rates (18.9% vs 26.4% at t=0.80), but also slightly higher grouping (71.2% vs 69.7%). The larger model better separates unrelated-but-similar names.

## Strengths

- **Semantic understanding**: Can group names that share no surface-level features. For instance, abbreviated forms like "gen. Štefánika" and the full "Generála Štefánika" produce similar embeddings because the model understands the words contextually.
- **Language-agnostic**: Works across languages without any language-specific rules. The multilingual training covers 50+ languages.
- **Diacritics-aware**: Unlike the deterministic methods that discard diacritics, the transformer model can use diacritical marks as meaningful features.
- **No hand-crafted rules**: Does not require suffix lists, street type dictionaries, or any domain-specific configuration.

## Weaknesses

### 1. High collision rate

The biggest issue. Semantic similarity conflates text similarity with entity identity. Two different people whose names look similar (Medvecká vs Medvecký, Chalupka vs Chalupková) get merged because the model treats them as near-synonyms. This is fundamentally different from the deterministic methods' failure modes.

### 2. Greedy ordering dependency

Same as all other clustering methods — results depend on processing order.

### 3. Computational cost

- Requires ~470 MB – 1.1 GB of model weights in memory
- First run downloads models from Hugging Face (~seconds to minutes)
- Encoding is ~100x slower than character-level methods (seconds vs milliseconds for 724 names)
- Requires PyTorch + transformers as dependencies (~500 MB installed)

### 4. Black-box behavior

Unlike suffix stripping (where you can trace exactly why two names merged), the embedding similarity is opaque. A cosine score of 0.82 gives no insight into which features the model found similar. This makes debugging problematic groupings difficult.

## How it differs from deterministic methods

| Aspect                 | Deterministic                                   | Embedding                                |
|------------------------|-------------------------------------------------|------------------------------------------|
| Input                  | ASCII-normalized                                | Original (with diacritics)               |
| Similarity             | Character-level (edit distance, n-gram overlap) | Dense vector cosine similarity           |
| Understands morphology | No (except suffix stripping)                    | Partially (via training data)            |
| Collision tendency     | Low (5–10%)                                     | High (19–26%)                            |
| Dependencies           | None / rapidfuzz                                | PyTorch, sentence-transformers           |
| Reproducibility        | Deterministic                                   | Deterministic (given same model version) |
| Explainability         | High (traceable rules)                          | Low (black-box)                          |
