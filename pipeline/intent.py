from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import BaseModel, Field
from typing import Literal, Optional
from config import OPENAI_API_KEY, OPENAI_BASE_URL, LLM_MODEL, _is_ollama
from pipeline.state import PipelineState, IntentResult
from pipeline.intent_rules import prefilter

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
                  ALSO: "dashboard KPIs", "show dashboard", "show me the KPIs", "KPIs", "dashboard"
past_report     → wants full report for a PAST date
revenue         → revenue / earnings / kitna hua / income
expenses        → kharcha / spending / expenditure
top_dishes      → all-time bestsellers / popular dishes overall (NO specific date)
todays_items    → what sold today OR on a specific date
                  ALSO: "top items yesterday", "top selling 2 days ago", "kal kya bika" — whenever
                  a date is involved, use todays_items (NOT top_dishes)
peak_hours      → busiest hours / rush time / peak time
customer_dues   → all customers with balances (no specific phone)
customer_balance → ONE specific customer's balance (user gave phone/name)
orders          → order list / order details
menu            → dish menu / what's served / price list / specific dish price
consumables     → chai / gutka / cigarette usage
                  ALSO: "drinks", "beverages", "peene ka", "chai serve karte ho" — anything about
                  beverages or what to drink → consumables (chai is tracked there, not on menu)
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
}

## Examples (learn the tricky boundaries from these)
"aaj kitna hua?" → {"intent":"revenue","date_hint":null,"phone":null,"confidence":0.95,"max_price":null,"min_price":null,"category_filter":null,"search_term":null,"period":"today"}
"kaisa raha aaj?" → {"intent":"daily_report","date_hint":null,"phone":null,"confidence":0.9,"max_price":null,"min_price":null,"category_filter":null,"search_term":null,"period":null}
"good day or slow day?" → {"intent":"daily_report","date_hint":null,"phone":null,"confidence":0.85,"max_price":null,"min_price":null,"category_filter":null,"search_term":null,"period":null}
"kal ke top items?" → {"intent":"todays_items","date_hint":"kal","phone":null,"confidence":0.95,"max_price":null,"min_price":null,"category_filter":null,"search_term":null,"period":null}
"best selling dishes?" → {"intent":"top_dishes","date_hint":null,"phone":null,"confidence":0.9,"max_price":null,"min_price":null,"category_filter":null,"search_term":null,"period":null}
"is hafte ka revenue?" → {"intent":"revenue","date_hint":"this week","phone":null,"confidence":0.95,"max_price":null,"min_price":null,"category_filter":null,"search_term":null,"period":"week"}
"kal kaisa raha?" → {"intent":"past_report","date_hint":"kal","phone":null,"confidence":0.9,"max_price":null,"min_price":null,"category_filter":null,"search_term":null,"period":null}
"chai serve karte ho?" → {"intent":"consumables","date_hint":null,"phone":null,"confidence":0.85,"max_price":null,"min_price":null,"category_filter":null,"search_term":null,"period":null}
"veg dishes under 50?" → {"intent":"menu","date_hint":null,"phone":null,"confidence":0.95,"max_price":50,"min_price":null,"category_filter":"veg","search_term":null,"period":null}
"who owes us money?" → {"intent":"customer_dues","date_hint":null,"phone":null,"confidence":0.95,"max_price":null,"min_price":null,"category_filter":null,"search_term":null,"period":null}
"what about the second one?" → {"intent":"general","date_hint":null,"phone":null,"confidence":0.8,"max_price":null,"min_price":null,"category_filter":null,"search_term":null,"period":null}
"is mahine trend kaisa hai?" → {"intent":"historical_trend","date_hint":"this month","phone":null,"confidence":0.9,"max_price":null,"min_price":null,"category_filter":null,"search_term":null,"period":null}
"what were the top selling items 2 days ago?" → {"intent":"todays_items","date_hint":"2 days ago","phone":null,"confidence":0.9,"max_price":null,"min_price":null,"category_filter":null,"search_term":null,"period":null}
"yesterday's payment split — cash vs upi?" → {"intent":"past_report","date_hint":"yesterday","phone":null,"confidence":0.9,"max_price":null,"min_price":null,"category_filter":null,"search_term":null,"period":null}
"what was yesterday's revenue?" → {"intent":"revenue","date_hint":"yesterday","phone":null,"confidence":0.95,"max_price":null,"min_price":null,"category_filter":null,"search_term":null,"period":null}
"what drinks or beverages do you serve?" → {"intent":"consumables","date_hint":null,"phone":null,"confidence":0.85,"max_price":null,"min_price":null,"category_filter":null,"search_term":null,"period":null}
"what dal dishes do you serve?" → {"intent":"menu","date_hint":null,"phone":null,"confidence":0.9,"max_price":null,"min_price":null,"category_filter":null,"search_term":"dal","period":null}
"what snacks/rice/roti do you have?" → {"intent":"menu","date_hint":null,"phone":null,"confidence":0.9,"max_price":null,"min_price":null,"category_filter":null,"search_term":null,"period":null}"""


_base = ChatOpenAI(
    base_url=OPENAI_BASE_URL,
    api_key=OPENAI_API_KEY,
    model=LLM_MODEL,
    temperature=0,
)
# Strict json_schema on OpenAI (gpt-4.1-nano supports it — far more reliable
# than json_mode). Ollama lacks strict schema, so it keeps json_mode.
if _is_ollama:
    _llm = _base.bind(extra_body={"think": False}).with_structured_output(_Schema, method="json_mode")
else:
    _llm = _base.with_structured_output(_Schema, method="json_schema", strict=True)


def _empty_intent() -> IntentResult:
    return {
        "intent": "general", "date_hint": None, "phone": None, "confidence": 0.0,
        "max_price": None, "min_price": None, "category_filter": None,
        "search_term": None, "period": None,
    }


async def classify_intent(state: PipelineState) -> dict:
    # 1) Deterministic pre-filter — unambiguous queries skip the LLM entirely.
    ruled = prefilter(state["query"])
    if ruled is not None:
        intent = {**_empty_intent(), **ruled}
        return {"intent": intent}

    # 2) LLM classification for everything else.
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
