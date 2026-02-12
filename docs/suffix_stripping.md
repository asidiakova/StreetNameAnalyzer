# Suffix Stripping (baseline)

**File**: `src/suffix_stripping.py`
**Type**: Rule-based, deterministic
**Language-specific**: Yes (Slovak morphology)

## Algorithm

1. **ASCII normalize** the input name (shared `text_utils.ascii_norm`): Unicode → ASCII, lowercase, collapse whitespace
2. **Handle ordinals**: If a token matches a number pattern (e.g., "1.", "9."), combine it with the next meaningful token as the group key (e.g., "1. mája" → `"1_maja"`)
3. **Remove street type tokens**: Filter out words like "ulica", "cesta", "námestie", "trieda", etc.
4. **Remove single-letter initials**: Filter out tokens like "M.", "R.", "J." (already reduced to "m", "r", "j" by ASCII normalization)
5. **Strip suffix from last token**: Apply longest-matching Slovak morphological suffix removal (e.g., `-ová` → remove, `-ovo` → remove, `-ského` → remove), requiring at least 3 characters remain as the stem
6. **Return the stem** as the group key

### Suffix list

Sorted longest-first for greedy matching:
`ovskeho`, `ovskej`, `ovska`, `ovske`, `sky`, `ska`, `ske`, `ski`, `ova`, `ovo`, `eho`, `ej`, `ov`, `a`, `o`, `u`, `y`, `i`

Minimum stem length: 3 characters (prevents over-stripping short names).

## Example

| Input | ASCII normalized | After filtering | Last token | Stem |
|-------|-----------------|-----------------|------------|------|
| "Štefánikova" | "stefanikova" | ["stefanikova"] | "stefanikova" | **"stefanik"** |
| "M. R. Štefánika" | "m r stefanika" | ["stefanika"] | "stefanika" | **"stefanik"** |
| "Námestie Ľ. Štúra" | "namestie l stura" | ["stura"] | "stura" | **"stur"** |
| "Štúrova" | "sturova" | ["sturova"] | "sturova" | **"stur"** |
| "1. mája" | "1 maja" | ordinal detected | — | **"1_maja"** |

## Evaluation Results

| Metric | Value |
|--------|-------|
| Grouping Rate | 94.7% |
| Collision Rate | 5.4% |
| Groups | 240 (from 729 variants, 216 entities) |

## Strengths

- **Simple and fast**: Pure string manipulation, no external dependencies beyond `unidecode`
- **High grouping rate**: Successfully unifies most name variants (94.7%)
- **Handles common Slovak patterns well**: Adjective forms (-ová, -ovo), genitive (-a, -u), possessive (-ského, -ovej)

## Weaknesses

### 1. Over-merges different people with the same surname

The method strips to the surname stem, so all streets named after different people with the same surname collide:

- "Janka Kráľa" → `kral`
- "Fraňa Kráľa" → `kral`
- "Kráľovská cesta" → `kral`
- "Námestie Krista Kráľa" → `kral`

These refer to at least 3 different entities (Janko Kráľ the poet, Fraňo Kráľ the writer, Christ the King, and "Kráľovská" as an adjective meaning "royal").

### 2. Over-merges different groups sharing a common noun root

- "Československej armády" → `armad`
- "Červenej armády" → `armad`
- "Sovietskej armády" → `armad`
- "Slovenskej armády" → `armad`

All different armies merged into one group.

Similarly for "hrdinov" (Dukelských hrdinov, Padlých hrdinov, Dargovských hrdinov — different groups of heroes).

### 3. Over-merges unrelated places with common noun roots

- "Červená hora" → `hora`
- "Stará hora" → `hora`
- "Pavla Horova" → `hora` (this is actually a person, not a mountain)
- "Horská cesta" → `hora`

The word "hora" (mountain) is common enough that many unrelated streets get grouped.

### 4. Roman numeral grouping

- "Zelená voda II." → `ii`
- "Jána Pavla II." → `ii`
- "Sídlisko II" → `ii`

All streets ending with a Roman numeral get grouped together regardless of context.

### 5. Language-specific

The suffix list is tailored to Slovak morphology. It would need significant modification for Czech, Hungarian, or other languages, making it less portable than language-agnostic methods.
