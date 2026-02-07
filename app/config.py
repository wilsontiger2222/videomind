import os
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
API_KEYS = os.getenv("API_KEYS", "test-key-123").split(",")
DATA_DIR = os.getenv("DATA_DIR", "./data")
DATABASE_URL = os.path.join(DATA_DIR, "videomind.db")
FRAMES_DIR = os.path.join(DATA_DIR, "frames")
TEMP_DIR = os.path.join(DATA_DIR, "temp")
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
STRIPE_PRO_PRICE_ID = os.getenv("STRIPE_PRO_PRICE_ID", "price_pro_placeholder")
STRIPE_BUSINESS_PRICE_ID = os.getenv("STRIPE_BUSINESS_PRICE_ID", "price_biz_placeholder")
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY", "")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@videomind.ai")
