from dotenv import load_dotenv
import os
import logging as _logging

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
BILL_APP_URL = os.getenv("BILL_APP_URL", "http://localhost:5002")
BILL_APP_EMAIL = os.getenv("BILL_APP_EMAIL")
BILL_APP_PASSWORD = os.getenv("BILL_APP_PASSWORD")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "http://localhost:11434/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "llama3.2")
# Stronger model for the hardest queries (e.g. trend analysis). Empty = disabled
# (everything uses LLM_MODEL). Kept separate so escalation can be A/B'd cheaply.
ESCALATION_MODEL = os.getenv("ESCALATION_MODEL", "")
API_KEY = os.getenv("API_KEY")
JWT_SECRET = os.getenv("JWT_SECRET", "dhaba-ai-jwt-secret-change-in-prod")
DATABASE_URL = os.getenv("DATABASE_URL", "")


ALLOWED_ORIGINS = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "http://localhost:5174").split(",")]

_is_ollama = "11434" in OPENAI_BASE_URL or "ollama" in OPENAI_BASE_URL.lower()
EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text" if _is_ollama else "text-embedding-3-small")
EMBED_BASE_URL = os.getenv("EMBED_BASE_URL", OPENAI_BASE_URL)
EMBED_API_KEY = os.getenv("EMBED_API_KEY", OPENAI_API_KEY or "ollama")

_missing = [k for k, v in {"BILL_APP_EMAIL": BILL_APP_EMAIL, "BILL_APP_PASSWORD": BILL_APP_PASSWORD, "API_KEY": API_KEY, "DATABASE_URL": DATABASE_URL}.items() if not v]
if _missing:
    _logging.warning(f"Missing env vars (app will start but tools may fail): {', '.join(_missing)}")
