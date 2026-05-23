from pipeline.state import PipelineState

# Tools where an empty list/result is NORMAL business state — not an error
_EMPTY_OK = {
    "get_expenses",
    "get_orders",
    "get_all_customer_ledgers",
    "get_customer_balance",
}

# Minimum tools that must succeed for each intent — if these fail, response is blocked
_REQUIRED = {
    "daily_report":      {"get_dashboard_kpis"},
    "past_report":       {"get_earnings_history"},
    "revenue":           {"get_dashboard_kpis", "get_earnings_history"},
    "expenses":          {"get_expenses"},
    "top_dishes":        {"get_top_dishes"},
    "todays_items":      {"get_todays_top_items"},
    "peak_hours":        {"get_peak_hours_today"},
    "customer_dues":     {"get_all_customer_ledgers"},
    "customer_balance":  {"get_customer_balance"},
    "orders":            {"get_orders"},
    "menu":              {"get_all_dishes"},
    "consumables":       {"get_consumables_summary"},
    "historical_trend":  {"get_earnings_history"},
    "general":           set(),
}


def verify_results(state: PipelineState) -> dict:
    intent_name = state["intent"]["intent"]
    raw = state["raw_results"]
    results = raw["results"]
    errors = raw["errors"]

    issues = []
    passed = True

    # Check tool errors
    for tool, err in errors.items():
        issues.append(f"{tool} failed: {err}")

    # If any REQUIRED tool errored → block the response
    required = _REQUIRED.get(intent_name, set())
    failed_required = required & set(errors.keys())
    if failed_required:
        passed = False
        issues.append(f"Critical tools unavailable: {', '.join(failed_required)}")

    # If ALL tools failed → Bill-App is likely down
    if errors and not results:
        passed = False
        issues.append("Bill-App appears to be unreachable — all tools failed")

    return {
        "verified": {
            "data": results,
            "issues": issues,
            "passed": passed,
        }
    }
