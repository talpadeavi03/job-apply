"""AetherApply global settings and configuration loader."""
import os
from pathlib import Path
from typing import Any, Dict
import yaml
from dotenv import load_dotenv

# Base paths
ROOT_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT_DIR / "config"
DATA_DIR = ROOT_DIR / "data"
LOGS_DIR = ROOT_DIR / "logs"
SCREENSHOTS_DIR = ROOT_DIR / "screenshots"
STORAGE_DIR = ROOT_DIR / "storage"

# Ensure runtime directories exist
for directory in [DATA_DIR, LOGS_DIR, SCREENSHOTS_DIR, STORAGE_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# Load environment variables
load_dotenv(ROOT_DIR / ".env")

# Resume path
RESUME_PATH = ROOT_DIR / "AT_26_AI.pdf"

# Database URL: Prioritize PostgreSQL (Neon/Supabase) via DATABASE_URL; fallback to SQLite
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    DATABASE_URL = f"sqlite:///{DATA_DIR / 'aetherapply.sqlite3'}"

# Gmail API Credentials
GMAIL_CLIENT_ID = os.getenv("GMAIL_CLIENT_ID", "")
GMAIL_CLIENT_SECRET = os.getenv("GMAIL_CLIENT_SECRET", "")
GMAIL_REFRESH_TOKEN = os.getenv("GMAIL_REFRESH_TOKEN", "")

# Gemini API Key (for MCP AI reasoning & form question answering)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Discord Webhook for Run Notifications
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")

# Platform Session Authentication (for Auto-Apply)
LINKEDIN_LI_AT = os.getenv("LINKEDIN_LI_AT", "")
LINKEDIN_USERNAME = os.getenv("LINKEDIN_USERNAME") or os.getenv("LINKEDIN_EMAIL", "")
LINKEDIN_PASSWORD = os.getenv("LINKEDIN_PASSWORD", "")
NAUKRI_AT = os.getenv("NAUKRI_AT", "")
NAUKRI_COOKIES = os.getenv("NAUKRI_COOKIES", "")
NAUKRI_USERNAME = os.getenv("NAUKRI_USERNAME") or os.getenv("NAUKRI_EMAIL", "")
NAUKRI_PASSWORD = os.getenv("NAUKRI_PASSWORD", "")

# Candidate Master Profile Details
CANDIDATE_NAME = "Avinash Vishnu Talpade"
CANDIDATE_EMAIL = "talpadeavi0303@gmail.com"
CANDIDATE_PHONE = "8999285015"
CANDIDATE_LOCATION = "Pune, Maharashtra, India"
CANDIDATE_CURRENT_CTC = os.getenv("CURRENT_CTC", "450000")
CANDIDATE_EXPECTED_CTC = os.getenv("EXPECTED_CTC", "750000")
CANDIDATE_NOTICE_PERIOD_DAYS = os.getenv("NOTICE_PERIOD_DAYS", "0")
CANDIDATE_NOTICE_ANSWER = os.getenv("RAG_NOTICE_ANSWER", "Immediate joiner (0 days)")
CANDIDATE_AVAILABILITY = os.getenv("RAG_AVAILABILITY", "Immediate")


def load_platforms_config() -> Dict[str, Any]:
    """Loads platform configuration from YAML file."""
    config_file = CONFIG_DIR / "platforms.yaml"
    if not config_file.exists():
        return {}
    with open(config_file, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}
