from openai import AsyncOpenAI
from config import OPENAI_API_KEY, OPENAI_BASE_URL, LLM_MODEL

client = AsyncOpenAI(
    api_key=OPENAI_API_KEY,
    base_url=OPENAI_BASE_URL,
)


async def chat(messages: list[dict], tools: list[dict] | None = None) -> dict:
    response = await client.chat.completions.create(
        model=LLM_MODEL,
        messages=messages,
        tools=tools,
    )
    return response.choices[0].message


# async generator — yields tokens one at a time as LLM produces them
# JS equivalent: async function* chatStream(messages) { yield token; }
async def chat_stream(messages: list[dict]):
    stream = await client.chat.completions.create(
        model=LLM_MODEL,
        messages=messages,
        stream=True,
    )
    async for chunk in stream:
        token = chunk.choices[0].delta.content
        if token:
            yield token
