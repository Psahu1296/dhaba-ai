import asyncio
import chromadb
from datetime import date, timedelta
from tools.bill_app import login, get_earnings_history, get_todays_top_items, get_peak_hours_today, get_consumables_summary

_chroma = chromadb.PersistentClient(path="./chroma_db")
_collection = _chroma.get_or_create_collection(
    name="daily_summaries",
    metadata={"hnsw:space": "cosine"},
)


def _build_summary_text(target_date: str, earnings, top_items, peak_hours, consumables) -> str:
    revenue = earnings.get("data", {})
    # earnings history returns array — find the entry for target_date
    entries = revenue if isinstance(revenue, list) else []
    day_entry = next((e for e in entries if str(e.get("date", "")).startswith(target_date)), None)
    revenue_val = day_entry.get("totalEarnings", "unknown") if day_entry else "unknown"

    items = top_items.get("top_items", [])
    items_text = ", ".join(f"{i['name']} ({i['quantity']})" for i in items[:5])

    peak = peak_hours.get("peak_hour", "unknown")
    peak_count = peak_hours.get("peak_order_count", "")

    tea = consumables.get("tea", {})
    consumables_text = f"tea sold: {tea.get('totalSold', 0)}"

    return (
        f"Date: {target_date} | Revenue: {revenue_val} | "
        f"Top items: {items_text} | Peak hour: {peak} ({peak_count} orders) | "
        f"{consumables_text}"
    )


async def embed_day(target_date: str = None):
    target = target_date or str(date.today() - timedelta(days=1))

    earnings, top_items, peak_hours, consumables = await asyncio.gather(
        get_earnings_history(period="day", num_periods=1),
        get_todays_top_items(date=target),
        get_peak_hours_today(date=target),
        get_consumables_summary(date=target),
    )

    text = _build_summary_text(target, earnings, top_items, peak_hours, consumables)
    print(f"Embedding: {text}")

    _collection.upsert(
        ids=[target],
        documents=[text],
        metadatas=[{"date": target}],
    )
    print(f"✓ Embedded summary for {target}")


def search_daily_summaries(query: str, n_results: int = 5) -> list:
    results = _collection.query(query_texts=[query], n_results=n_results)
    return results["documents"][0] if results["documents"] else []


if __name__ == "__main__":
    asyncio.run(embed_day())
