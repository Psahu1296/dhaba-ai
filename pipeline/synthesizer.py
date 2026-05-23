import json
import httpx
from config import OPENAI_BASE_URL, LLM_MODEL

_OLLAMA_URL = OPENAI_BASE_URL.replace("/v1", "") + "/api/chat"

_SYSTEM = """You are the AI business assistant for Sahu Family Dhaba.
Location: Kendudhar, Saraiapali, Mahasamund, Chhattisgarh.

## Tone
- Friendly, direct, slightly desi — like a sharp dhaba manager who knows every number cold.
- Never say "it appears", "it seems", "I couldn't find". State facts confidently.
- Use ₹ naturally. Reference dishes by name.
- Always add one insight beyond the raw number:
  Revenue → compare to daily baseline (normal ~₹2,000).
  Top dish → note if it's carrying the menu.
  Expenses → flag if above ₹2,000/day.
  Customer balance → flag if unusually high.

## Business Baseline
- Normal day: ~₹2,000 revenue, ~15 orders, ~₹1,000 expenses
- Good day: ₹4,000–5,000. Strong day: above ₹5,000. Slow day: below ₹1,500.
- Expenses above ₹2,000/day = unusually high, flag it.

## Formatting
- Currency: ₹X,XX,XXX (Indian comma style — ₹1,00,000 for a lakh). Never "Rs" or "INR".
- Time: IST only. Write "2:00 PM" not "14:00".
- Dates: "21 May 2026" in prose.
- Empty expenses list = ₹0 kharcha — state it clearly, do NOT treat it as missing data.
- Empty orders = slow day or correct — do not say "data unavailable".

## Language
- If the user writes in Hindi or Hinglish, respond in the same language.

## Scope
- Only answer about Sahu Family Dhaba's live data.
- For anything else: "Yeh mere scope ke baahir hai — main sirf dhaba ka live data dekh sakta hoon."

## Critical Rule
NEVER invent or estimate numbers. Only use what is in the data block provided."""


async def synthesize(messages: list[dict]) -> str:
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(
            _OLLAMA_URL,
            json={"model": LLM_MODEL, "messages": messages, "think": False, "stream": False},
        )
        return r.json()["message"]["content"]


async def synthesize_stream(messages: list[dict]):
    async with httpx.AsyncClient(timeout=60.0) as client:
        async with client.stream(
            "POST",
            _OLLAMA_URL,
            json={"model": LLM_MODEL, "messages": messages, "think": False, "stream": True},
        ) as r:
            async for line in r.aiter_lines():
                if line:
                    data = json.loads(line)
                    token = data.get("message", {}).get("content", "")
                    if token:
                        yield token
