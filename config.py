import os
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()

# Monitoring channels
MONITORING_CHANNELS = [
    "ghonetv",
    "joynewsontv",
]

# Deployment Info
DEPLOY_VERSION = "1.0.8-LibFix-17:32"

# Telegram
TG_API_ID = int(os.getenv("TG_API_ID", 0))
TG_API_HASH = os.getenv("TG_API_HASH")
TG_PHONE = os.getenv("TG_PHONE")
TG_SESSION_STRING = os.getenv("TG_SESSION_STRING", "").strip().strip("'").strip('"')

# Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Notifications
NOTIFIER_BOT_TOKEN = os.getenv("NOTIFIER_BOT_TOKEN")
USER_CHAT_ID = os.getenv("USER_CHAT_ID")

# Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

# X / Twitter (Playwright session — no API key needed)
X_SESSION_COOKIES = os.getenv("X_SESSION_COOKIES", "")  # base64-encoded JSON from capture_x_session.py
X_USERNAME = os.getenv("X_USERNAME", "")  # your X handle (for logging)

# Bot Settings
POLLING_INTERVAL = int(os.getenv("POLLING_INTERVAL_MINUTES", 15)) * 60
POSTING_INTERVAL = int(os.getenv("POSTING_INTERVAL_MINUTES", 20)) * 60
MAX_POSTS_PER_DAY = int(os.getenv("MAX_POSTS_PER_DAY", 50))
DEBUG = os.getenv("DEBUG", "True").lower() == "true"

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MEDIA_TEMP_DIR = os.path.join(BASE_DIR, "temp_media")
PROMPTS_DIR = os.path.join(BASE_DIR, "prompts")

# Ensure temp directory exists
if not os.path.exists(MEDIA_TEMP_DIR):
    os.makedirs(MEDIA_TEMP_DIR)
