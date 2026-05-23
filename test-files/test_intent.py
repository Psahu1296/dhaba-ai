import asyncio
from pipeline.intent import classify_intent

queries = [
    'aaj kitna hua?',
    'give me today full report',
    'kal ke expenses kya the?',
    'who owes us the most?',
    'veg dishes kya hain?',
]

async def test():
    for q in queries:
        result = await classify_intent({
            'query': q, 'role': 'admin',
            'intent': None, 'plan': None,
            'raw_results': None, 'verified': None,
            'response': None, 'messages': []
        })
        i = result["intent"]
        hint = f'  date_hint={i["date_hint"]!r}' if i["date_hint"] else ''
        print(f'{q!r:45} → {i["intent"]} ({i["confidence"]:.2f}){hint}')

asyncio.run(test())
