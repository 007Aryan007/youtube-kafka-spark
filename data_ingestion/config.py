import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

API_KEY = os.getenv("YOUTUBE_API_KEY", "Enter your API key")
KAFKA_BROKER = os.getenv("KAFKA_BROKER", "localhost:9092")
TOPIC = os.getenv("TOPIC", "youtube-data")

REGIONS = ["IN", "US", "GB", "CA", "AU"]
CATEGORY_IDS = ["1", "2", "10", "15", "17", "20", "22", "23", "24", "25", "26", "28"]

MAX_RESULTS = 50
PAGES_PER_CATEGORY = 1
POLL_SECONDS = 45
REQUEST_TIMEOUT = 20
CHANNEL_BATCH_SIZE = 50
DESCRIPTION_LIMIT = 500


