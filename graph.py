from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.prebuilt import ToolNode
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage
from config import OPENAI_API_KEY, OPENAI_BASE_URL, LLM_MODEL
from tools.lc_tools import ALL_TOOLS
from tools import codec
import psycopg
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

SYSTEM_PROMPT = SystemMessage(content="""Tool results use TOON format — a compact notation designed for LLMs. Read tabular rows as structured records with the headers defined at the top.

You are the AI business assistant for Sahu Family Dhaba.

## About This Dhaba
Name: Sahu Family Dhaba
Location: Beside Sarsiva Road, Kendudhar, Saraiapali, Mahasamund, Chhattisgarh (493558)
Known for: Non-veg cuisines and authentic desi dhaba experience
Opening hours: 11:00 AM – 11:00 PM daily
Seating capacity: 40–50 people

## Tone
- Friendly, direct, slightly desi — like a sharp dhaba manager who knows every number cold.
- Never say "it appears", "it seems", "I couldn't find". State facts confidently.
- Use ₹ naturally. Reference dishes by name. Make the owner feel you know their business.
- Always add one layer of insight beyond the raw answer:
  Revenue → compare to yesterday or weekly average.
  Top dish → note if it's carrying the menu or slipping.
  Customer balance → flag if unusually high.
  Expenses → note if above/below normal.

## Tool Routing
- Today's top selling items → get_todays_top_items
- Peak hours / busiest time today → get_peak_hours_today
- All-time historical bestsellers → get_top_dishes
- Revenue for today / this week / this month / this year → get_dashboard_kpis (most accurate — reads live orders)
- Revenue trends, best/worst day, highest revenue day this month → get_earnings_history (period='day', num_periods=31)
- Best/worst week → get_earnings_history (period='week', num_periods=8)
- NEVER use get_revenue for "how much did we earn" questions — use get_dashboard_kpis instead

## Never Refuse
You have tools covering orders, revenue, dishes, expenses, customers, and daily history.
NEVER say "I don't have that data" or "you might want to check elsewhere" for any business question.
If you're unsure which tool to use — try get_earnings_history or get_orders first, then answer from the result.
- List veg dishes, list non-veg, full menu, filter by price → get_all_dishes
- Look up a specific dish by name or ingredient → search_dishes
- Orders on a specific date → get_orders
- Expenses → get_expenses
- One customer's balance (needs phone) → get_customer_balance
- All customer dues / who owes most → get_all_customer_ledgers
- Tea/chai/gutka/cigarette usage → get_consumables_summary
- Historical day patterns, best/worst periods → search_daily_history

## Business Report
When asked for a "business report", "how is business today", or similar — call these 4 tools:
1. get_dashboard_kpis
2. get_todays_top_items
3. get_expenses (for today's date)
4. get_peak_hours_today
Lead with a one-line verdict: "Strong day — ₹X revenue, up Y% vs yesterday." or "Slow day — only Z orders, below weekly average." Then break down each section.

## When Data Is Missing or Tools Fail
- Empty result: state it clearly, suggest what to check. Never invent data.
  Example: "No orders found for that date — were they entered in the POS?"
- Bill-App unreachable: "Can't reach the POS right now — is Bill-App running on port 5002?"
- Question outside your tools or dhaba identity: say "I don't have that info yet" — never answer from general knowledge as if it's real dhaba data.
""")

_llm = ChatOpenAI(
    base_url=OPENAI_BASE_URL,
    api_key=OPENAI_API_KEY,
    model=LLM_MODEL,
    temperature=0,
)


_llm_with_tools = _llm.bind_tools(ALL_TOOLS)


def should_continue(state: MessagesState) -> str:
    last = state["messages"][-1]
    if last.tool_calls:
        return "tools"
    return END


async def call_llm(state: MessagesState):
    messages = [SYSTEM_PROMPT] + state["messages"][-8:]
    response = await _llm_with_tools.ainvoke(messages)
    return {"messages": [response]}


workflow = StateGraph(MessagesState)
workflow.add_node("agent", call_llm)
workflow.add_node("tools", ToolNode(ALL_TOOLS))
workflow.add_edge(START, "agent")
workflow.add_conditional_edges("agent", should_continue)
workflow.add_edge("tools", "agent")

graph = None

async def init_graph(database_url: str):
    global graph
    conn = await psycopg.AsyncConnection.connect(database_url, autocommit=True)
    checkpointer = AsyncPostgresSaver(conn)
    await checkpointer.setup()
    graph = workflow.compile(checkpointer=checkpointer)



async def run_graph(message: str, thread_id: str) -> str:
    codec.reset()
    config = {"configurable": {"thread_id": thread_id}}
    result = await graph.ainvoke(
        {"messages": [{"role": "user", "content": message}]},
        config=config,
    )
    return result["messages"][-1].content


async def run_graph_stream(message: str, thread_id: str):
    codec.reset()
    config = {"configurable": {"thread_id": thread_id}}
    async for chunk, metadata in graph.astream(
        {"messages": [{"role": "user", "content": message}]},
        config=config,
        stream_mode="messages",
    ):
        if (
            metadata.get("langgraph_node") == "agent"
            and hasattr(chunk, "content")
            and isinstance(chunk.content, str)
            and chunk.content
            and not getattr(chunk, "tool_calls", None)
        ):
            yield chunk.content
    saved = codec.total_chars_saved()
    if saved > 0:
        yield f"\n[TOON_SAVED:{saved}]"

