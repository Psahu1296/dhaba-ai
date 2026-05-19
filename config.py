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
