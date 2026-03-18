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

This downloads the Slovakia OSM extract, loads it into PostGIS with `osm2pgsql`, creates the vector-tile function, and starts Martin.

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

All Python commands are run from the `src/` directory:

```bash
cd src
```

| Step                   | Command                              | Output                                                           |
|------------------------|--------------------------------------|------------------------------------------------------------------|
| Extract street lengths | `python -m analysis.compute`         | `analysis/street_lengths.csv`                                    |
| Build ground truth     | `python -m analysis.ground_truth`    | `analysis/ground_truth.csv`, `analysis/ground_truth_grouped.csv` |
| Evaluate methods       | `python -m analysis.evaluate`        | `analysis/evaluation.json`                                       |
| Export mappings (FE)   | `python -m analysis.export_mappings` | `analysis/mappings.json`                                         |

Run a single method with `--methods`:

```bash
python -m analysis.evaluate --methods suffix_stripping levenshtein
```

Available methods: `suffix_stripping`, `levenshtein`, `ngram`, `llm_gpt4o_mini`, `llm_claude_haiku`, `llm_gemini_flash`.

## Configuration

`src/config.py` contains tunable constants. Defaults work out of the box, but can be adjusted:

| Constant                                 | Default                      | Editable | Description                                                                  |
|------------------------------------------|------------------------------|----------|------------------------------------------------------------------------------|
| `DB_TABLE`                               | `planet_osm_line`            | No       | PostGIS table created by osm2pgsql, must match the import                    |
| `REQUEST_DELAY`                          | `0.1`                        | Yes      | Delay (seconds) between Wikidata API requests                                |
| `WIKIDATA_TIMEOUT`                       | `10`                         | Yes      | Timeout (seconds) for each Wikidata request                                  |
| `CONFIDENCE_THRESHOLD`                   | `0.7`                        | Yes      | Minimum score to include a street in ground truth                            |
| `CONFIDENCE_EXACT` / `_STEM` / `_PREFIX` | `1.0` / `0.9` / `0.7`        | Yes      | Scores assigned by match type when comparing street names to Wikidata labels |
| `WIKIDATA_LABEL_LANGUAGES`               | `["sk","cs","en","de","hu"]` | Yes      | Languages fetched from Wikidata for label matching; adjust for other regions |
| `PROBLEM_ENTITIES_TOP_N`                 | `10`                         | Yes      | Number of worst-performing entities shown in evaluation output               |
| `COLLISIONS_DISPLAY_N`                   | `10`                         | Yes      | Number of collision examples shown in evaluation output                      |

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
