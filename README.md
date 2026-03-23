# StreetNameAnalyzer

Compares deterministic and AI-based methods for normalizing Slovak street names from OpenStreetMap data. Evaluates suffix stripping, Levenshtein distance, N-gram similarity, and LLM-based classification (GPT-4o-mini, Claude Haiku, Gemini Flash) against a Wikidata-derived ground truth.

## Prerequisites

- Docker & Docker Compose
- Python 3.10+
- API keys for OpenAI, Anthropic, and Google Gemini (for LLM methods)

## Setup

**1. Start infrastructure** (PostGIS + Martin tile server):

```bash
# Linux / macOS
./setup.sh

# Windows (PowerShell)
.\setup.ps1
```

This downloads the .pbf file for Slovakia from geofabrik, loads it into PostGIS with `osm2pgsql`, creates the vector-tile function, and starts Martin.

If you already have a `.osm.pbf` file, place it at `data/slovakia-latest.osm.pbf` before running the script.

**2. Configure environment:**

```bash
cp src/.env.example src/.env
# Edit src/.env and fill in your API keys
```

**3. Install Python dependencies:**

```bash
pip install -r requirements.txt
```

## Usage

All Python commands are run from the **project root**:

| Step                   | Command                                  | Output                                                                   |
|------------------------|------------------------------------------|--------------------------------------------------------------------------|
| Extract street lengths | `python -m src.analysis.compute`         | `src/analysis/street_lengths.csv`                                        |
| Build ground truth     | `python -m src.analysis.ground_truth`    | `src/analysis/ground_truth.csv`, `src/analysis/ground_truth_grouped.csv` |
| Export mappings        | `python -m src.analysis.export_mappings` | `src/analysis/mappings.json`                                             |
| Evaluate methods       | `python -m src.analysis.evaluate`        | `src/analysis/evaluation.json`                                           |


Run a single method with `--method`:

```bash
python -m src.analysis.evaluate --method suffix_stripping
```

Available methods: `suffix_stripping`, `levenshtein`, `ngram`, `llm_gpt4o_mini`, `llm_claude_haiku`, `llm_gemini_flash`.

## Configuration

`src/config.py` contains tunable constants and parameters for analysis

| Constant                                 | Default                      | Description                                                                  |
|------------------------------------------|------------------------------|------------------------------------------------------------------------------|
| `REQUEST_DELAY`                          | `0.1`                        | Delay (seconds) between Wikidata API requests                                |
| `WIKIDATA_TIMEOUT`                       | `10`                         | Timeout (seconds) for each Wikidata request                                  |
| `CONFIDENCE_THRESHOLD`                   | `0.7`                        | Minimum score to include a street in ground truth                            |
| `CONFIDENCE_EXACT` / `_STEM` / `_PREFIX` | `1.0` / `0.9` / `0.7`        | Scores assigned by match type when comparing street names to Wikidata labels |
| `WIKIDATA_LABEL_LANGUAGES`               | `["sk","cs","en","de","hu"]` | Languages fetched from Wikidata for label matching;                          |
| `PROBLEM_ENTITIES_TOP_N`                 | `10`                         | Number of worst-performing entities shown in evaluation output               |
| `COLLISIONS_DISPLAY_N`                   | `10`                         | Number of collision examples shown in evaluation output                      |
| `LEVENSHTEIN_RATIO_THRESHOLD`            | `0.8`                        | Min Levenshtein.ratio (0–1) to merge into an existing cluster                |
| `NGRAM_SIZE`                             | `3`                          | Character n-gram length for n-gram Jaccard clustering                        |
| `NGRAM_JACCARD_THRESHOLD`                | `0.5`                        | Min Jaccard similarity (0–1) to merge into an existing cluster               |
| `LLM_FALLBACK_ON_ERROR`                  | `True`                       | If False, LLM failures cache `""` and are skipped in export/eval             |

## Project Structure

```
├── docker-compose.yml        # PostGIS + Martin services
├── martin.yaml               # Martin tile server config
├── docker/
│   ├── postgis.Dockerfile    # PostGIS image with osm2pgsql
│   └── init.sql              # streets() vector-tile function
├── setup.sh / setup.ps1      # One-command infrastructure setup
├── requirements.txt
└── src/
    ├── config.py             # Shared constants
    ├── text_utils.py         # Text preprocessing utilities
    ├── normalization_methods/
    │   ├── suffix_stripping/  # Rule-based baseline
    │   ├── levenshtein/       # Edit-distance clustering
    │   ├── ngram/             # Jaccard similarity clustering
    │   └── llm/               # LLM-based classification
    └── analysis/
        ├── compute.py         # Street length aggregation
        ├── ground_truth.py    # Wikidata ground truth extraction
        ├── evaluate.py        # Method evaluation (grouping/collision rates)
        └── export_mappings.py # JSON export for frontend
```

## Services

| Service | URL                     |
|---------|-------------------------|
| PostGIS | `localhost:5434`        |
| Martin  | `http://localhost:3001` |
