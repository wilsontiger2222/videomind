import os
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
API_KEYS = os.getenv("API_KEYS", "test-key-123").split(",")
DATA_DIR = os.getenv("DATA_DIR", "./data")
DATABASE_URL = os.path.join(DATA_DIR, "videomind.db")
FRAMES_DIR = os.path.join(DATA_DIR, "frames")
TEMP_DIR = os.path.join(DATA_DIR, "temp")
