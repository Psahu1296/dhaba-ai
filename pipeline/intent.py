from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import BaseModel, Field
from typing import Literal, Optional
from config import OPENAI_API_KEY, OPENAI_BASE_URL, LLM_MODEL
from pipeline.state import PipelineState, IntentResult

INTENT_TYPES = Literal[
    "daily_report",      # full report for today
    "past_report",       # full report for a past date
    "revenue",           # revenue / earnings / kitna hua
    "expenses",          # kharcha / spending
    "top_dishes",        # all-time bestsellers
    "todays_items",      # what sold on a specific day
    "peak_hours",        # busiest hours
    "customer_dues",     # all customers with balances
    "customer_balance",  # one specific customer (has phone)
    "orders",            # order list / details
    "menu",              # dish menu / search
    "consumables",       # chai / gutka / cigarette
    "historical_trend",  # patterns spanning weeks/months
    "general",           # out of scope / greeting / chitchat
]


class _Schema(BaseModel):
    intent: INTENT_TYPES
    date_hint: Optional[str] = Field(None, description="Relative time phrase from user e.g. 'kal', 'last week'")
    phone: Optional[str] = Field(None, description="Phone number if user is asking about a specific customer")
    confidence: float = Field(..., ge=0.0, le=1.0)
    max_price: Optional[float] = Field(None, description="Max price in ₹ e.g. 50 from 'under ₹50' — menu intent only")
    min_price: Optional[float] = Field(None, description="Min price in ₹ e.g. 100 from 'above ₹100' — menu intent only")
    category_filter: Optional[str] = Field(None, description="'veg', 'non-veg', or 'egg' — menu intent only")
    search_term: Optional[str] = Field(None, description="Specific dish name searched e.g. 'biryani' — menu intent only")
    period: Optional[str] = Field(None, description="'today', 'week', 'month', or 'year' — revenue intent only")


_PROMPT = """You are an intent classifier for a dhaba (Indian restaurant) business assistant.

Classify the user query into exactly one intent:

daily_report    → wants full business report for TODAY
past_report     → wants full report for a PAST date
revenue         → revenue / earnings / kitna hua / income
expenses        → kharcha / spending / expenditure
top_dishes      → all-time bestsellers / popular dishes overall
todays_items    → what sold today OR on a specific date
peak_hours      → busiest hours / rush time / peak time
customer_dues   → all customers with balances (no specific phone)
customer_balance → ONE specific customer's balance (user gave phone/name)
orders          → order list / order details
menu            → dish menu / what's served / price list
consumables     → chai / gutka / cigarette usage
historical_trend → patterns / comparisons spanning weeks or months
general         → out of scope / greeting / chitchat / unclear
                  OR a follow-up that refers to a previous answer and needs no new data
                  (e.g. "what about the second one?", "tell me more about that", "and them?",
                   "uske baad kaun?", "compare that", "who is next on the list?")
                  When in doubt between a business intent and a follow-up, prefer general.
                  IMPORTANT: Business performance questions are NOT general —
                  "good day or slow day?", "kaisa raha aaj?", "was today busy?" → daily_report
                  "kitna kamaya?" without context → revenue

Also extract:
- date_hint: any time reference ("kal", "yesterday", "last week") — null if none
- phone: phone number if asking about specific customer — null otherwise
- confidence: how sure you are (0.0–1.0)
- max_price: max price in ₹ if user says "under ₹X" or "less than ₹X" — number only, null otherwise
- min_price: min price in ₹ if user says "above ₹X" or "more than ₹X" — number only, null otherwise
- category_filter: "veg", "non-veg", or "egg" if user filters by category — null otherwise
- search_term: specific dish/item name being searched (e.g. "biryani", "chicken") — null otherwise
- period: "today", "week", "month", or "year" for revenue queries — null otherwise

Respond ONLY with valid JSON in this exact shape:
{
  "intent": "<one of the intent values above>",
  "date_hint": "<time phrase or null>",
  "phone": "<phone number or null>",
  "confidence": <0.0 to 1.0>,
  "max_price": <number or null>,
  "min_price": <number or null>,
  "category_filter": "<veg|non-veg|egg or null>",
  "search_term": "<dish name or null>",
  "period": "<today|week|month|year or null>"
}"""


_llm = ChatOpenAI(
    base_url=OPENAI_BASE_URL,
    api_key=OPENAI_API_KEY,
    model=LLM_MODEL,
    temperature=0,
).with_structured_output(_Schema, method="json_mode")


async def classify_intent(state: PipelineState) -> dict:
    result: _Schema = await _llm.ainvoke([
        SystemMessage(content=_PROMPT),
        HumanMessage(content=state["query"]),
    ])
    intent: IntentResult = {
        "intent":          result.intent,
        "date_hint":       result.date_hint,
        "phone":           result.phone,
        "confidence":      result.confidence,
        "max_price":       result.max_price,
        "min_price":       result.min_price,
        "category_filter": result.category_filter,
        "search_term":     result.search_term,
        "period":          result.period,
    }
    return {"intent": intent}
