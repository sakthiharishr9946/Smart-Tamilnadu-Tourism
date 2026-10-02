import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "").strip()
GROQ_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-20b").strip()

DATABASE_DIR = BASE_DIR / "database"
DATABASE_PATH = DATABASE_DIR / "tourism.db"

MODELS_DIR = BASE_DIR / "models"

CROWD_MODEL_DIR = (
    MODELS_DIR
    / "crowd_prediction"
    / "saved"
)

RECOMMENDATION_MODEL_DIR = (
    MODELS_DIR
    / "recommendation"
    / "saved"
)

DATA_DIR = BASE_DIR / "data"

UI_DIR = BASE_DIR / "ui"

DEFAULT_START_TIME = "09:00"

DEFAULT_TRIP_DAYS = 3

DEFAULT_TRAVELERS = 2


def ensure_directories():
    directories = [
        DATABASE_DIR,
        CROWD_MODEL_DIR,
        RECOMMENDATION_MODEL_DIR,
        DATA_DIR,
        UI_DIR,
    ]

    for directory in directories:
        directory.mkdir(
            parents=True,
            exist_ok=True,
        )