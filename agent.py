import json
import asyncio
from llm import chat, chat_stream
from tools.definitions import TOOLS
from tools.bill_app import login, get_top_dishes, get_dashboard_kpis, get_orders, get_expenses, get_customer_balance, get_revenue
from tools.retriever import search_dishes


TOOL_MAP = {
    "get_top_dishes": get_top_dishes,
    "get_dashboard_kpis": get_dashboard_kpis,
    "get_orders": get_orders,
    "get_expenses": get_expenses,
    "get_customer_balance": get_customer_balance,
    "get_revenue": get_revenue,
    "search_dishes": search_dishes,
}


def _base_messages(user_message: str) -> list[dict]:
    return [
        {
            "role": "system",
            "content": (
                "You are a helpful assistant for a dhaba (Indian restaurant). "
                "Use the available tools to answer questions about the business. "
                "Always use tools when asked about dishes, revenue, or orders."
            ),
        },
        {"role": "user", "content": user_message},
    ]


# Shared helper — resolves tool calls, returns messages ready for final answer
# Both run_agent and run_agent_stream use this
async def _resolve_tools(user_message: str) -> list[dict]:
    messages = _base_messages(user_message)
    response = await chat(messages, tools=TOOLS)

    tool_calls = response.tool_calls
    is_text_format = False

    if not tool_calls and response.content:
        try:
            parsed = json.loads(response.content)
            if "name" in parsed and parsed["name"] in TOOL_MAP:
                tool_calls = [parsed]
                is_text_format = True
        except json.JSONDecodeError:
            pass

    if not tool_calls:
        # No tool needed — return messages as-is, final answer already in response
        messages.append({"role": "assistant", "content": response.content})
        return messages

    if not is_text_format:
        messages.append(response)

    for tool_call in tool_calls:
        if is_text_format:
            name = tool_call["name"]
            args = tool_call.get("arguments", {})
            call_id = "text_call_0"
        else:
            name = tool_call.function.name
            args = json.loads(tool_call.function.arguments)
            call_id = tool_call.id

        print(f"→ Calling tool: {name}({args})")
        fn = TOOL_MAP.get(name)
        result = await fn(**args) if fn else {"error": f"Unknown tool: {name}"}

        messages.append({
            "role": "tool",
            "tool_call_id": call_id,
            "content": json.dumps(result),
        })

    return messages


# Non-streaming — returns full answer string
async def run_agent(user_message: str) -> str:
    messages = await _resolve_tools(user_message)
    last = messages[-1]
    # If last message is already assistant (no tool was called), return it
    if last.get("role") == "assistant":
        return last["content"]
    final = await chat(messages)
    return final.content


# Streaming — yields tokens as LLM generates them
async def run_agent_stream(user_message: str):
    messages = await _resolve_tools(user_message)
    last = messages[-1]
    if last.get("role") == "assistant":
        # No tool was called — yield the existing content as one chunk
        yield last["content"]
        return
    async for token in chat_stream(messages):
        yield token


async def main():
    await login()
    questions = [
        "What are the top 3 selling dishes?",
        "How is the business doing today?",
    ]
    for q in questions:
        print(f"\nQ: {q}")
        answer = await run_agent(q)
        print(f"A: {answer}")


if __name__ == "__main__":
    asyncio.run(main())
