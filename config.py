"""
Configuration File
==================
Credentials are loaded from the .env file (never hardcoded here).

Setup:
  1. Ensure .env exists in this folder (copy from .env.example)
  2. Fill in your real values in .env
  3. .env is in .gitignore — never committed

Non-sensitive settings (selectors, date format, category mapping)
remain here since they are not secrets.
"""

import os
from dotenv import load_dotenv

# Load .env from project root — MUST be called before reading env vars
_env_path = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(dotenv_path=_env_path)


def _require(key: str) -> str:
    """Read a required env var — raise clearly if missing."""
    val = os.environ.get(key)
    if not val:
        raise EnvironmentError(
            f"\nMissing required secret: {key}\n"
            f"Add it to your .env file:\n"
            f"  {key}=your_value_here\n"
            f"Then restart."
        )
    return val


# ─────────────────────────────────────────────────────────────────
# SECRETS  (loaded from .env — never hardcoded)
# ─────────────────────────────────────────────────────────────────
ECW_URL      = _require("ECW_URL")
ECW_USERNAME = _require("ECW_USERNAME")
ECW_PASSWORD = _require("ECW_PASSWORD")

GOOGLE_CLOUD_PROJECT_ID      = os.environ.get("GOOGLE_CLOUD_PROJECT_ID", "")
GOOGLE_CLOUD_LOCATION        = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
GOOGLE_APPLICATION_CREDENTIALS = os.environ.get(
    "GOOGLE_APPLICATION_CREDENTIALS", "config/google_service_account.json"
)

# Set the Google creds env var that google-auth looks for
if GOOGLE_APPLICATION_CREDENTIALS:
    os.environ.setdefault(
        "GOOGLE_APPLICATION_CREDENTIALS", GOOGLE_APPLICATION_CREDENTIALS
    )

# ─────────────────────────────────────────────────────────────────
# LOCAL MISTRAL OCR  (runs 100% on your machine)
# ─────────────────────────────────────────────────────────────────
OLLAMA_HOST       = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
MISTRAL_OCR_MODEL = os.environ.get("MISTRAL_OCR_MODEL", "mistral-small3.1")

# ─────────────────────────────────────────────────────────────────
# NON-SECRET SETTINGS
# ─────────────────────────────────────────────────────────────────
ECW_DATE_FORMAT = "%m/%d/%Y"   # Date format ECW expects

# ─────────────────────────────────────────────────────────────────
# CATEGORY -> STAFF GROUP MAPPING
# Map AI category names to exact group names in ECW's Send To Staff dialog
# ─────────────────────────────────────────────────────────────────
CATEGORY_TO_FOLDER = {
    "BIOLOGICS":        "Group Biologics",
    "PRIOR_AUTH":       "Group PA",
    "LABS":             "Group Labs",
    "MEDICAL_RECORDS":  "Group Medical Records",
    "MEDICATION_AND_IT":"Group MA",
    "RADIOLOGY":        "Group Radiology",
    "UNKNOWN":          None    # Triggers manual review
}
