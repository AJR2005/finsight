import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'finsight.db'}")
# Render/Heroku style URLs use "postgres://", which SQLAlchemy no longer accepts.
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
TOKEN_EXPIRE_MINUTES = int(os.getenv("TOKEN_EXPIRE_MINUTES", "1440"))

# Set to "0" to stop the app calling Yahoo Finance / mfapi.in (e.g. in tests or offline).
LIVE_PRICES = os.getenv("LIVE_PRICES", "1") == "1"

SEED_DEMO = os.getenv("SEED_DEMO", "1") == "1"
DEMO_EMAIL = "demo@finsight.app"
DEMO_PASSWORD = "demo1234"

FRONTEND_DIST = Path(os.getenv("FRONTEND_DIST", BASE_DIR.parent / "frontend" / "dist"))
