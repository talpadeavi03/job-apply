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

# Discord Webhook for Run Notifications
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")

# Platform Session Authentication (for Auto-Apply)
LINKEDIN_LI_AT = os.getenv("LINKEDIN_LI_AT", "")

# Candidate Master Profile Details
CANDIDATE_NAME = "Avinash Vishnu Talpade"
CANDIDATE_EMAIL = "talpadeavi0303@gmail.com"
CANDIDATE_PHONE = "8999285015"
CANDIDATE_LOCATION = "Pune, Maharashtra, India"


def load_platforms_config() -> Dict[str, Any]:
    """Loads platform configuration from YAML file."""
    config_file = CONFIG_DIR / "platforms.yaml"
    if not config_file.exists():
        return {}
    with open(config_file, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}
