from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.prebuilt import ToolNode
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage
from config import OPENAI_API_KEY, OPENAI_BASE_URL, LLM_MODEL
from tools.lc_tools import ALL_TOOLS

SYSTEM_PROMPT = SystemMessage(content=(
    "You are a business assistant for a dhaba (Indian restaurant). "
    "Use tools to answer questions. Key routing rules:\n"
    "- Today's top items / most sold today → get_todays_top_items\n"
    "- Peak hours / busiest time today → get_peak_hours_today\n"
    "- get_top_dishes is ALL-TIME data, never for today-specific queries\n"
    "- Revenue trends, best week, historical performance → get_earnings_history\n"
    "- Revenue for a period total → get_revenue with period: day/week/month/year\n"
    "- Who owes money, customer dues → get_all_customer_ledgers\n"
    "- Chai/cigarette/gutka usage → get_consumables_summary\n"
    "- Business reports → call multiple tools for complete data\n"
    "- Historical daily patterns, best/worst days → search_daily_history"
))

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
    messages = [SYSTEM_PROMPT] + state["messages"]
    response = await _llm_with_tools.ainvoke(messages)
    return {"messages": [response]}


workflow = StateGraph(MessagesState)
workflow.add_node("agent", call_llm)
workflow.add_node("tools", ToolNode(ALL_TOOLS))
workflow.add_edge(START, "agent")
workflow.add_conditional_edges("agent", should_continue)
workflow.add_edge("tools", "agent")

from langgraph.checkpoint.memory import MemorySaver

_checkpointer = MemorySaver()
graph = workflow.compile(checkpointer=_checkpointer)


async def run_graph(message: str, thread_id: str) -> str:
    config = {"configurable": {"thread_id": thread_id}}
    result = await graph.ainvoke(
        {"messages": [{"role": "user", "content": message}]},
        config=config,
    )
    return result["messages"][-1].content


async def run_graph_stream(message: str, thread_id: str):
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

