from pathlib import Path
import os

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parents[1]
STORAGE_DIR = Path(os.getenv("APP_STORAGE_DIR", BASE_DIR / "storage")).resolve()
MODEL_NAME = os.getenv("GROQ_MODEL", "openai/gpt-oss-safeguard-20b")
