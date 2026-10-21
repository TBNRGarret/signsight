import os
import json

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
TAXONOMY_PATH = os.path.join(DATA_DIR, "taxonomy.json")

# Model & Training parameters
NUM_CLASSES = 10
IMAGE_SIZE = (64, 64)  # High resolution enough for sign symbols, lightweight for edge/web
BATCH_SIZE = 64
LEARNING_RATE = 1e-3
NUM_EPOCHS = 15
CONFIDENCE_THRESHOLD = 0.70  # Below this, sign is flagged as 'is_uncertain'

# Expiration policies per sign type (in days)
EXPIRATION_POLICIES = {
    "W.227": 14,      # Temporary road work (short lifecycle)
    "W.245a": 60,     # General caution / road hazard
    "P.125": 180,     # No overtaking (semi-permanent)
    "P.127 (50)": 365,# Speed limit 50 km/h (permanent)
    "P.127 (60)": 365,# Speed limit 60 km/h (permanent)
    "P.127 (80)": 365,# Speed limit 80 km/h (permanent)
    "P.122": 365,     # STOP sign (permanent)
    "P.102": 365,     # No entry (permanent)
    "R.301a": 365,    # Ahead only (permanent)
    "R.301e": 365     # Keep right (permanent)
}

# Duplicate detection threshold
DUPLICATE_DISTANCE_THRESHOLD_METERS = 30.0  # meters

def load_taxonomy():
    if os.path.exists(TAXONOMY_PATH):
        with open(TAXONOMY_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

TAXONOMY = load_taxonomy()
CLASS_MAPPING = {item["new_id"]: item for item in TAXONOMY}
