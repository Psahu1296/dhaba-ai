from pipeline.state import PipelineState

# Tools where an empty list/result is NORMAL business state — not an error.
# Documented for reference; emptiness never blocks a response (empty = zero,
# not broken). The synthesizer prompt handles narrating empty states.
_EMPTY_OK = {
    "get_expenses",
    "get_orders",
    "get_all_customer_ledgers",
    "get_customer_balance",
}


# Per-intent data-sanity checks. Each takes the tool results dict and returns a
# list of human-readable problems. A non-empty list blocks the response — we'd
# rather say "data unavailable" than emit a confident wrong number.
def _sanity_issues(intent_name: str, results: dict) -> list[str]:
    issues: list[str] = []

    def _num(d, *keys):
        for k in keys:
            v = (d or {}).get(k)
            if v is not None:
                try:
                    return float(v)
                except (TypeError, ValueError):
                    return None
        return None

    if intent_name in ("daily_report", "past_report"):
        summary = results.get("get_daily_summary") or {}
        kpis = results.get("get_dashboard_kpis") or {}
        orders = _num(summary, "order_count")
        revenue = _num(summary, "revenue", "revenue_rupees")
        # Orders exist but revenue is zero → almost certainly a stale/broken
        # aggregation, not a real free-of-charge day. Block rather than mislead.
        if orders and orders > 0 and revenue == 0:
            issues.append("revenue is ₹0 despite orders existing — figures look stale")
        # daily_report leans on KPIs; a missing today figure is suspicious.
        if intent_name == "daily_report" and kpis and _num(kpis, "today_revenue_rupees", "today") is None:
            issues.append("dashboard returned no today revenue")

    return issues


def verify_results(state: PipelineState) -> dict:
    intent_name = state["intent"]["intent"]
    primary_tool = state.get("primary_tool")
    raw = state["raw_results"]
    results = raw["results"]
    errors = raw["errors"]

    issues: list[str] = []
    passed = True

    # Surface every tool error for the trace/log.
    for tool, err in errors.items():
        issues.append(f"{tool} failed: {err}")

    # The answer depends on the primary tool. If it never produced a result
    # (errored, or simply absent), block — downstream prose would be ungrounded.
    if primary_tool and primary_tool not in results:
        passed = False
        issues.append(f"Critical tool unavailable: {primary_tool}")

    # If EVERY tool failed, Bill-App is likely unreachable.
    if errors and not results:
        passed = False
        issues.append("Bill-App appears to be unreachable — all tools failed")

    # Data-sanity checks (e.g. orders>0 but revenue==0).
    sanity = _sanity_issues(intent_name, results)
    if sanity:
        passed = False
        issues.extend(sanity)

    return {
        "verified": {
            "data": results,
            "issues": issues,
            "passed": passed,
        }
    }
