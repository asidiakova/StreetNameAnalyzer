from dotenv import load_dotenv

load_dotenv()

DB_TABLE = "planet_osm_line"

GROUND_TRUTH_CSV = "ground_truth.csv"
GROUND_TRUTH_GROUPED_CSV = "ground_truth_grouped.csv"
EVALUATION_OUTPUT_DEFAULT = "evaluation.json"
COMPUTE_OUTPUT_DEFAULT = "street_lengths.csv"
MAPPINGS_OUTPUT_DEFAULT = "mappings.json"

REQUEST_DELAY = 0.1
WIKIDATA_TIMEOUT = 10
CONFIDENCE_THRESHOLD = 0.7
CONFIDENCE_EXACT = 1.0
CONFIDENCE_STEM = 0.9
CONFIDENCE_PREFIX = 0.7

WIKIDATA_LABEL_LANGUAGES = ["sk", "cs", "en", "de", "hu"]

PROBLEM_ENTITIES_TOP_N = 10
COLLISIONS_DISPLAY_N = 10