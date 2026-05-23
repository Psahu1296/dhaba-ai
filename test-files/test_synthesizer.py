import asyncio
from pipeline.synthesizer import synthesize_response

async def test():
    base = {
        "query": "give me today full report",
        "role": "admin",
        "intent": {"intent": "daily_report", "date_hint": "today", "phone": None, "confidence": 1.0},
        "plan": None, "raw_results": None, "messages": [],
    }

    # Test 1: all data present
    state = {**base, "verified": {
        "passed": True,
        "issues": [],
        "data": {
            "get_dashboard_kpis": {"today_revenue_rupees": 2100, "today_vs_yesterday_pct": 5, "week_revenue_rupees": 10478},
            "get_todays_top_items": {"top_items": [{"name": "Chicken Masala", "quantity": 8}, {"name": "Roti", "quantity": 15}]},
            "get_peak_hours_today": {"peak_hour": "13:00 – 14:00", "peak_order_count": 7},
            "get_expenses": {"expenses": [], "total_rupees": 0},
        },
    }}
    result = await synthesize_response(state)
    print("=== Daily Report ===")
    print(result["response"])

    # Test 2: verification failed
    state2 = {**base, "verified": {
        "passed": False,
        "issues": ["get_dashboard_kpis failed: Connection refused", "Critical tools unavailable: get_dashboard_kpis"],
        "data": {},
    }}
    result2 = await synthesize_response(state2)
    print("\n=== Bill-App Down ===")
    print(result2["response"])

asyncio.run(test())
