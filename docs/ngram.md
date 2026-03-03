# N-gram Jaccard Similarity

**File**: `src/ngram_method.py`
**Type**: Similarity-based (set), stateful
**Language-specific**: No

## Algorithm

1. **Preprocess** the input name (shared `text_utils.preprocess_name`): ASCII normalize, remove street types, remove initials, keep all remaining tokens
2. **Generate character n-grams**: Break each token into overlapping character fragments of size N (default: 2 = bigrams), then combine all fragments into a single set
3. **Look up cache**: If this exact name was already processed, return the cached group ID
4. **Compare** the n-gram set to all existing group representatives using Jaccard similarity: `|A ∩ B| / |A ∪ B|`
5. **If best match ≥ threshold**: Join that group
6. **Otherwise**: Create a new group with this name as the representative

### Key parameters

- **N** (default: 2): N-gram size. Bigrams are standard for short strings — trigrams produce too few fragments for 3-4 character tokens, making comparisons unreliable.
- **Threshold** (default: 0.50): Minimum Jaccard similarity (0.0–1.0) to join a group.

### N-gram generation

N-grams are generated **per token**, then combined. This avoids creating misleading fragments across word boundaries.

Example: `"antona bernolaka"` (preprocessed from "Antona Bernoláka") → tokens `["antona", "bernolaka"]`
{'be', 'no', 'on', 'ak', 'an', 'rn', 'na', 'er', 'ol', 'nt', 'to', 'la', 'ka'}

### Jaccard similarity

Jaccard measures set overlap: `|A ∩ B| / |A ∪ B|`

Unlike Levenshtein (which compares character sequences position-by-position), Jaccard is position-independent — it only cares about which fragments appear, not where they appear in the string.

## Example

| Name A               | Name B           | Shared bigrams | Jaccard | Levenshtein |
|----------------------|------------------|----------------|---------|-------------|
| "stefanikova"        | "stefanikovo"    | 9 of 11        | 0.82    | 0.91        |
| "stefanikova"        | "stefanika"      | 8 of 10        | 0.80    | 0.87        |
| "namestie stefanika" | "stefanikova"    | 7 of 19        | 0.37    | ~0.40       |
| "sturova"            | "ludovita stura" | 4 of 13        | 0.31    | ~0.45       |

## Evaluation Results

Threshold sweep on 216 entities, 729 variants (bigrams, N=2):

| Threshold | Grouping Rate | Collision Rate | Groups  |
|-----------|---------------|----------------|---------|
| 0.25      | 81.9%         | 48.3%          | 143     |
| 0.30      | 85.0%         | 34.8%          | 178     |
| 0.35      | 84.5%         | 22.3%          | 224     |
| 0.40      | 83.3%         | 17.0%          | 253     |
| 0.45      | 80.6%         | 11.9%          | 295     |
| **0.50**  | **79.9%**     | **9.6%**       | **311** |
| 0.55      | 74.2%         | 6.5%           | 355     |
| 0.60      | 67.9%         | 5.8%           | 399     |

**Default threshold**: 0.50

### Comparison across all methods

| Method              | Grouping Rate | Collision Rate | Groups  |
|---------------------|---------------|----------------|---------|
| Suffix stripping    | 94.7%         | 5.4%           | 240     |
| **N-gram (t=0.50)** | **79.9%**     | **9.6%**       | **311** |
| Levenshtein (t=80)  | 63.6%         | 7.2%           | 418     |

N-gram fills the gap between suffix stripping (high grouping, language-specific) and Levenshtein (low grouping, language-agnostic), achieving significantly better grouping than Levenshtein while remaining language-agnostic.

## Strengths

- **Language-agnostic**: No Slovak-specific rules — works for any language
- **Position-independent**: Unlike Levenshtein, shared character fragments contribute to similarity regardless of where they appear in the string. This helps when the same name part appears at different positions (e.g., "Námestie Štefánika" vs "Štefánikova")
- **Significantly better grouping than Levenshtein**: 79.9% vs 63.6% at comparable collision rates. The set-based approach is more tolerant of extra tokens (like street types that slip through preprocessing, or added first names)
- **No external dependencies**: Uses only Python built-in set operations

## Weaknesses

### 1. No morphological understanding

Like Levenshtein, N-gram similarity operates at the character level. It cannot recognize that `-ová` and `-a` are grammatical endings. For names with very different surface forms (e.g., "sturova" vs "ludovita stura"), the shared bigrams are diluted by the extra content, resulting in low Jaccard scores (~0.31).

### 2. Greedy ordering dependency

Same as Levenshtein — the method processes names sequentially and the first name becomes the group representative. Different input ordering can produce different groupings.

### 3. Short-name sensitivity

Very short names (2-3 characters) produce only 1-2 bigrams, making Jaccard comparisons unreliable. A single shared bigram between two short names can produce a high Jaccard score by coincidence.

### 4. Threshold sensitivity

Like Levenshtein, the threshold is a single global parameter balancing grouping vs collision. However, N-gram's threshold range (0.0–1.0) operates on a different scale than Levenshtein's (0–100), making direct threshold comparison between the two methods unintuitive. The sweet spot tends to be around 0.40–0.55 for this dataset.

## How it differs from Levenshtein

Both are character-level similarity methods with greedy clustering, but they measure similarity differently:

- **Levenshtein** asks: "How many character edits (insert/delete/replace) to transform A into B?" — this is **sequential** and position-sensitive
- **N-gram Jaccard** asks: "What fraction of character fragments do A and B share?" — this is **set-based** and position-independent

The practical impact: N-gram is more forgiving of extra tokens and word reordering, which is why it achieves higher grouping rates. But it can also match unrelated strings that happen to share common fragments (like "ov", "sk", "an" which are frequent in Slovak), contributing to slightly higher collision rates.
