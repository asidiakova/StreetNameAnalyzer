# Levenshtein Greedy Clustering

**File**: `src/levenshtein_method.py`
**Type**: Similarity-based, stateful
**Language-specific**: No

## Algorithm

1. **Preprocess** the input name (shared `text_utils.ascii_norm`, then remove street types and initials — same as suffix stripping, but **keep all remaining tokens** instead of just the last one)
2. **Look up cache**: If this exact name was already processed, return the cached group ID
3. **Compare** the preprocessed name to all existing group representatives using `rapidfuzz.fuzz.ratio` (character-level similarity score, 0–100)
4. **If best match ≥ threshold**: Join that group
5. **Otherwise**: Create a new group with this name as the representative
6. **Return the group ID** (which is the preprocessed representative name)

The method is **stateful** — it builds groups incrementally as names are processed. Module-level state resets naturally between separate script runs.

### Key parameters

- **Threshold** (default: 80): Minimum similarity score to join an existing group. Higher = stricter (fewer merges, more groups). Lower = looser (more merges, fewer groups).

## Example

Processing order: "Štefánikova" → "Štefánikovo námestie" → "Komenského"

| Step | Input | Preprocessed | Best match | Score | Action |
|------|-------|-------------|------------|-------|--------|
| 1 | "Štefánikova" | "stefanikova" | — | — | New group: `"stefanikova"` |
| 2 | "Štefánikovo námestie" | "stefanikovo" | "stefanikova" | 91 | Joins `"stefanikova"` |
| 3 | "Komenského" | "komenskeho" | "stefanikova" | 50 | New group: `"komenskeho"` |

Note: "M. R. Štefánika" → preprocessed to `"stefanika"` → compared to `"stefanikova"` → score ≈ 87 → **joins** the group (above threshold 80). But "Ľudovíta Štúra" → `"ludovita stura"` → compared to `"stefanikova"` → score ≈ 30 → correctly starts a new group.

## Evaluation Results

Threshold sweep on 216 entities, 729 variants:

| Threshold | Grouping Rate | Collision Rate | Groups |
|-----------|---------------|----------------|--------|
| 70 | 71.7% | 20.2% | 302 |
| 75 | 68.2% | 11.8% | 365 |
| **80** | **63.6%** | **7.2%** | **418** |
| 85 | 59.8% | 4.3% | 463 |

**Default threshold**: 80 (collision rate close to suffix stripping baseline, while clearly showing the grouping tradeoff)

### Comparison with suffix stripping

| Metric | Suffix Stripping | Levenshtein (t=80) |
|--------|------------------|--------------------|
| Grouping Rate | 94.7% | 63.6% |
| Collision Rate | 5.4% | 7.2% |
| Groups | 240 | 418 |

## Strengths

- **Language-agnostic**: No Slovak-specific rules — works for any language where street name variants are character-similar
- **Catches typos and spelling variants**: "Štúrová" vs "Štúrova" (one diacritic difference) would be caught
- **Simple conceptually**: Just a similarity comparison + greedy assignment

## Weaknesses

### 1. No morphological understanding

Levenshtein counts character edits without understanding grammar. Names that are linguistically related but character-different score poorly:

- `fuzz.ratio("sturova", "ludovita stura")` ≈ 45% — far below any threshold
- `fuzz.ratio("stefanikova", "stefanika")` ≈ 87% — works, but only because the strings happen to overlap heavily

Suffix stripping knows that `-ova` and `-a` are grammatical endings and removes them; Levenshtein treats every character difference equally. This is the main reason for the grouping rate gap (94.7% vs 63.6%).

### 2. Greedy ordering dependency

Each name is compared **only to existing group representatives**, not to all other names. The first name processed becomes the representative, and that choice is permanent.

This means:
- Different input ordering can produce different groupings
- A name that could match multiple potential groups always joins whichever group was created first
- Two names that are similar to each other might end up in different groups if neither is similar enough to the current representative

A non-greedy alternative would compute all pairwise distances first (distance matrix), then use hierarchical clustering. This would eliminate ordering dependency but adds O(n²) complexity and requires `scipy` — significantly more complex for a marginal improvement, since the fundamental weakness (no morphological understanding) would remain.

### 3. Threshold sensitivity

The threshold is a single global parameter that must balance two opposing goals:
- **Low threshold** → better grouping (catches more variants) but more collisions (merges unrelated names)
- **High threshold** → fewer collisions but worse grouping (misses variants with low character similarity)

There is no threshold that achieves both high grouping and low collision rates, because the method cannot distinguish "similar because related" from "similar by coincidence".
