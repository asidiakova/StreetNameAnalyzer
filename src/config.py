from dotenv import load_dotenv

load_dotenv()

GROUND_TRUTH_CSV = "src/analysis/ground_truth.csv"
GROUND_TRUTH_GROUPED_CSV = "src/analysis/ground_truth_grouped.csv"
EVALUATION_OUTPUT_DEFAULT = "src/analysis/evaluation.json"
COMPUTE_OUTPUT_DEFAULT = "src/analysis/street_lengths.csv"
UNTAGGED_OUTPUT_DEFAULT = "src/analysis/untagged_streets.csv"
MAPPINGS_OUTPUT_DEFAULT = "src/analysis/mappings.json"

REQUEST_DELAY = 0.1
WIKIDATA_TIMEOUT = 10
CONFIDENCE_THRESHOLD = 0.7
CONFIDENCE_EXACT = 1.0
CONFIDENCE_STEM = 0.9
CONFIDENCE_PREFIX = 0.7

WIKIDATA_LABEL_LANGUAGES = ["sk", "cs", "en", "de", "hu"]

PROBLEM_ENTITIES_TOP_N = 10
COLLISIONS_DISPLAY_N = 10