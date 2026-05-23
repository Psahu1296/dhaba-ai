import chromadb
from datetime import date, timedelta
from tools.bill_app import get_daily_summary

_chroma = chromadb.PersistentClient(path="./chroma_db")
_collection = _chroma.get_or_create_collection(
    name="daily_summaries",
    metadata={"hnsw:space": "cosine"},
)


def _revenue_verdict(revenue: float) -> str:
    if revenue < 1500: return "slow"
    if revenue < 2000: return "below_average"
    if revenue < 4000: return "normal"
    if revenue < 5000: return "good"
    return "strong"


def _build_text(target: str, day_name: str, summary: dict) -> str:
    revenue  = float(summary.get("revenue", 0))
    expenses = float(summary.get("expenses", {}).get("total", 0))
    verdict  = _revenue_verdict(revenue)

    exp_breakdown = summary.get("expenses", {}).get("by_type", {})
    exp_text = ", ".join(f"{k}: ₹{int(v)}" for k, v in exp_breakdown.items()) or "none"

    payment  = summary.get("payment_split", {})

    top_qty  = summary.get("top_items_by_qty", [])
    qty_text = ", ".join(f"{i['name']} ({i['quantity']})" for i in top_qty[:5]) or "none"

    top_rev  = summary.get("top_items_by_revenue", [])
    rev_text = ", ".join(f"{i['name']} (₹{i['revenue']})" for i in top_rev[:5]) or "none"

    cons = summary.get("consumables", {})

    return (
        f"Date: {target} ({day_name}). "
        f"Revenue: ₹{revenue:.0f} — {verdict} day. "
        f"Expenses: ₹{expenses:.0f} ({exp_text}). Net: ₹{revenue - expenses:.0f}. "
        f"Orders: {summary.get('order_count', 0)} total, {summary.get('cancelled_count', 0)} cancelled, "
        f"{payment.get('credit', 0)} on credit. "
        f"Avg order value: ₹{summary.get('avg_order_value', 0)}. "
        f"Payment — Cash: {payment.get('cash', 0)}, UPI: {payment.get('upi', 0)}, "
        f"Card: {payment.get('card', 0)}, Credit: {payment.get('credit', 0)}. "
        f"Top by qty: {qty_text}. Top by revenue: {rev_text}. "
        f"Peak hour: {summary.get('peak_hour_ist', 'unknown')}. "
        f"First order: {summary.get('first_order_time_ist', 'unknown')}. "
        f"Consumables — Tea: {cons.get('tea', 0)}, "
        f"Gutka: {cons.get('gutka', 0)}, Cigarette: {cons.get('cigarette', 0)}."
    )


def _build_metadata(target: str, day_name: str, week_str: str, month_str: str, summary: dict) -> dict:
    revenue  = float(summary.get("revenue", 0))
    expenses = float(summary.get("expenses", {}).get("total", 0))
    return {
        "date":        target,
        "day_name":    day_name,
        "week":        week_str,
        "month":       month_str,
        "revenue":     revenue,
        "expenses":    expenses,
        "net_profit":  revenue - expenses,
        "verdict":     _revenue_verdict(revenue),
        "order_count": summary.get("order_count", 0),
    }


async def embed_from_summary(summary: dict) -> None:
    """Embed an already-fetched daily summary dict. Used by backfill to avoid re-fetching."""
    target = summary.get("date", "")
    if not target:
        return
    d         = date.fromisoformat(target)
    day_name  = d.strftime("%A")
    week_str  = d.strftime("%Y-W%W")
    month_str = d.strftime("%Y-%m")

    text     = _build_text(target, day_name, summary)
    metadata = _build_metadata(target, day_name, week_str, month_str, summary)

    print(f"Embedding {target}: {text[:140]}...")
    _collection.upsert(ids=[target], documents=[text], metadatas=[metadata])
    print(f"✓ Embedded {target}")


async def embed_day(target_date: str = None) -> None:
    """Fetch daily summary from Bill-App and embed into ChromaDB."""
    target  = target_date or str(date.today() - timedelta(days=1))
    summary = await get_daily_summary(target)
    if not summary:
        print(f"  skip {target} — no data returned")
        return
    await embed_from_summary(summary)


def search_daily_summaries(query: str, n_results: int = 5) -> list[dict]:
    results = _collection.query(query_texts=[query], n_results=n_results)
    docs    = results["documents"][0] if results["documents"] else []
    metas   = results["metadatas"][0] if results["metadatas"] else []
    return [{"text": d, "meta": m} for d, m in zip(docs, metas)]


def get_days_by_metadata(where: dict) -> list[dict]:
    """Fetch days by structured metadata filter. e.g. where={"month": "2026-05"}"""
    results = _collection.get(where=where, include=["documents", "metadatas"])
    docs    = results.get("documents", [])
    metas   = results.get("metadatas", [])
    return [{"text": d, "meta": m} for d, m in zip(docs, metas)]


if __name__ == "__main__":
    import asyncio
    from tools.bill_app import login

    async def _test():
        await login()
        await embed_day()

    asyncio.run(_test())
