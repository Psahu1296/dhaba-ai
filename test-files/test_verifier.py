from pipeline.verifier import verify_results

# Simulate: daily_report, all tools succeeded (normal run)
state_ok = {
    "intent": {"intent": "daily_report", "date_hint": "today", "phone": None, "confidence": 1.0},
    "raw_results": {
        "results": {
            "get_dashboard_kpis": {"today_revenue_rupees": 2100, "week_revenue_rupees": 10478},
            "get_todays_top_items": {"top_items": [{"name": "Roti", "quantity": 12}]},
            "get_peak_hours_today": {"peak_hour": "13:00", "peak_order_count": 5},
            "get_expenses": {"expenses": [], "total_rupees": 0},
        },
        "errors": {},
    },
}

# Simulate: KPI tool failed (Bill-App down for that call)
state_fail = {
    "intent": {"intent": "daily_report", "date_hint": "today", "phone": None, "confidence": 1.0},
    "raw_results": {
        "results": {"get_todays_top_items": {"top_items": []}},
        "errors": {"get_dashboard_kpis": "Connection refused"},
    },
}

for label, state in [("All OK", state_ok), ("KPI failed", state_fail)]:
    result = verify_results(state)
    v = result["verified"]
    print(f"\n[{label}]")
    print(f"  passed: {v['passed']}")
    print(f"  issues: {v['issues']}")
    print(f"  data keys: {list(v['data'].keys())}")
