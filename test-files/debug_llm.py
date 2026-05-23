import asyncio
import httpx
import json
from config import OPENAI_BASE_URL, LLM_MODEL

# Hit Ollama native API directly — bypasses LangChain entirely
OLLAMA_BASE = OPENAI_BASE_URL.replace("/v1", "")  # http://localhost:11434

async def debug():
    async with httpx.AsyncClient(timeout=30.0) as client:
        payload = {
            "model": LLM_MODEL,
            "messages": [{"role": "user", "content": "Say hello in one sentence."}],
            "think": False,
            "stream": False,
        }
        print(f"Hitting: {OLLAMA_BASE}/api/chat")
        print(f"Model: {LLM_MODEL}")
        r = await client.post(f"{OLLAMA_BASE}/api/chat", json=payload)
        data = r.json()
        print("\nFull response:")
        print(json.dumps(data.get("message", data), indent=2))

asyncio.run(debug())
