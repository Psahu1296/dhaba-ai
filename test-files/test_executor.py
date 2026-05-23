import asyncio
from pipeline.planner import plan_workflow
from pipeline.executor import execute_tools

async def test():
    state = {
        "query": "give me today full report",
        "role": "admin",
        "intent": {"intent": "daily_report", "date_hint": "today", "phone": None, "confidence": 1.0},
        "plan": None, "raw_results": None, "verified": None, "response": None, "messages": [],
    }

    state.update(plan_workflow(state))
    print("Plan:")
    for s in state["plan"]["steps"]:
        print(f"  → {s['tool_name']}({s['args']})")

    print("\nExecuting tools...")
    state.update(await execute_tools(state))

    print("\nResults:")
    for tool, result in state["raw_results"]["results"].items():
        print(f"  ✓ {tool}: {str(result)[:100]}")

    if state["raw_results"]["errors"]:
        print("\nErrors:")
        for tool, err in state["raw_results"]["errors"].items():
            print(f"  ✗ {tool}: {err}")

asyncio.run(test())
