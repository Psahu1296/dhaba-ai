"""
One-time backfill script: embeds all historical daily summaries into ChromaDB.
Fetches the full date range in a single API call via /api/daily-summary/range,
then embeds each day. Run once; nightly embed_day() handles new days going forward.

Usage:
    python3 scripts/backfill_rag.py                          # uses default START_DATE
    python3 scripts/backfill_rag.py 2026-03-01               # custom start
    python3 scripts/backfill_rag.py 2026-03-01 2026-05-22    # custom range
"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from datetime import date, timedelta
from tools.bill_app import login, get_daily_summary_range
from tools.daily_embedder import embed_from_summary

START_DATE = "2026-02-01"


async def backfill(start: str = START_DATE, end: str = None):
    end = end or str(date.today() - timedelta(days=1))

    await login()

    print(f"Fetching daily summaries {start} → {end} (one API call)...")
    summaries = await get_daily_summary_range(start, end)
    print(f"Got {len(summaries)} days from Bill-App.\n")

    ok = skipped = failed = 0
    for summary in summaries:
        target = summary.get("date", "")
        if not target:
            continue
        if float(summary.get("revenue", 0)) == 0:
            print(f"  skip {target} — zero revenue")
            skipped += 1
            continue
        try:
            await embed_from_summary(summary)
            ok += 1
        except Exception as e:
            print(f"  ✗ {target} — {e}")
            failed += 1

    print(f"\nDone. ✓ {ok} embedded | ↷ {skipped} skipped | ✗ {failed} failed")


if __name__ == "__main__":
    start = sys.argv[1] if len(sys.argv) > 1 else START_DATE
    end   = sys.argv[2] if len(sys.argv) > 2 else None
    asyncio.run(backfill(start, end))
