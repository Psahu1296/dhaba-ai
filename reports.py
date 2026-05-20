import logging
from datetime import date
from graph import run_graph
from db import save_daily_report

logger = logging.getLogger(__name__)

REPORT_THREAD_PREFIX = "daily-report"

REPORT_PROMPT = """/no_think
Generate a comprehensive daily business report for Sahu Family Dhaba.

Include these sections:
1. Revenue Summary — today's earnings vs yesterday, vs weekly average
2. Top Dishes Today — what sold most, what didn't move
3. Peak Hours — when was it busiest
4. Expenses — today's costs, anything unusual
5. One Key Insight — one actionable recommendation for tomorrow

Be direct and specific. Use ₹ for amounts. Format with clear headings.
If any data is unavailable, say so briefly and move on."""


async def generate_daily_report(target_date: str = None) -> str:
    report_date = target_date or date.today().isoformat()
    thread_id = f"{REPORT_THREAD_PREFIX}-{report_date}"

    logger.info(f"Generating daily report for {report_date}")

    prompt = f"Today is {report_date}. {REPORT_PROMPT}"
    content = await run_graph(prompt, thread_id=thread_id)

    await save_daily_report(report_date, content)
    logger.info(f"Daily report saved for {report_date}")

    return content
