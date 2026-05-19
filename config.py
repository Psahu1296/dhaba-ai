from dotenv import load_dotenv
import os

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
BILL_APP_URL = os.getenv("BILL_APP_URL", "http://localhost:5002")
BILL_APP_EMAIL = os.getenv("BILL_APP_EMAIL")
BILL_APP_PASSWORD = os.getenv("BILL_APP_PASSWORD")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "http://localhost:11434/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "llama3.2")
API_KEY = os.getenv("API_KEY")

_is_ollama = "11434" in OPENAI_BASE_URL or "ollama" in OPENAI_BASE_URL.lower()
EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text" if _is_ollama else "text-embedding-3-small")
EMBED_BASE_URL = os.getenv("EMBED_BASE_URL", OPENAI_BASE_URL)
EMBED_API_KEY = os.getenv("EMBED_API_KEY", OPENAI_API_KEY or "ollama")
