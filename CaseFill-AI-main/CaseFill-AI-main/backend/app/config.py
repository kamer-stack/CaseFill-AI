"""
Configuration management for CaseFill-AI backend.
Loads environment variables from .env or API_Key.env files.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Try loading from .env first, then API_Key.env (like the original prototype)
_env_file = Path(".env")
if _env_file.exists():
    load_dotenv(str(_env_file))
else:
    _alt_env = Path("API_Key.env")
    if _alt_env.exists():
        load_dotenv(str(_alt_env))

# DashScope API configuration
API_KEY = os.getenv("API_KEY", "")
BASE_URL = os.getenv("BASE_URL", "https://dashscope-intl.aliyuncs.com/compatible-mode/v1")

# Qwen model names
QWEN_VL_MODEL = os.getenv("QWEN_VL_MODEL", "qwen-vl-max")
QWEN_TEXT_MODEL = os.getenv("QWEN_TEXT_MODEL", "qwen-plus")

# OCR.space (used ONLY for B-form and old-format CNIC — see ocr_space_client.py)
OCR_SPACE_API_KEY = os.getenv("OCR_SPACE_API_KEY", "")
OCR_SPACE_URL = os.getenv("OCR_SPACE_URL", "https://api.ocr.space/parse/image")

# Server configuration
PORT = int(os.getenv("PORT", "8000"))
HOST = os.getenv("HOST", "0.0.0.0")

# Database
DATABASE_PATH = os.getenv("DATABASE_PATH", "casefill.db")

# Uploads directory
UPLOADS_DIR = Path(os.getenv("UPLOADS_DIR", "uploads"))
UPLOADS_DIR.mkdir(exist_ok=True)

# Session configuration
SESSION_EXPIRY_DAYS = 7
SESSION_SECRET = os.getenv("SESSION_SECRET", "casefill-ai-dev-secret-change-in-production")
