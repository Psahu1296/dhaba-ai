import asyncio
from config import DATABASE_URL
from pipeline.graph import init_pipeline, run_pipeline

async def test():
    await init_pipeline(DATABASE_URL)

    queries = [
        ("give me today full report", "test-session-1"),
        ("aaj kitna hua?",            "test-session-2"),
        ("who owes us the most?",     "test-session-3"),
    ]

    for query, session in queries:
        print(f"\n{'─'*50}")
        print(f"Q: {query!r}")
        response = await run_pipeline(query, session)
        print(f"A: {response}")

asyncio.run(test())
