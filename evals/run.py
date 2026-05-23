import asyncio
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from config import DATABASE_URL
from tools.bill_app import login
from pipeline.graph import init_pipeline, run_pipeline


async def run_evals():
    await login()
    await init_pipeline(DATABASE_URL)
    print("✓ Logged into Bill-App + pipeline ready\n")

    with open("evals/questions.json") as f:
        questions = json.load(f)

    results = []

    for q in questions:
        print(f"[{q['id']:02d}/{len(questions)}] {q['question']}")
        try:
            session_id = f"eval-v2-{q['id']}"
            answer = await run_pipeline(q["question"], session_id=session_id, role="admin")
            status = "ok"
        except Exception as e:
            answer = f"ERROR: {e}"
            status = "error"

        results.append({
            "id":              q["id"],
            "question":        q["question"],
            "expected_topics": q["expected_topics"],
            "answer":          answer,
            "status":          status,
        })
        preview = answer[:100].replace("\n", " ")
        print(f"  → {preview}{'...' if len(answer) > 100 else ''}\n")

    with open("evals/results.json", "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    ok_count = sum(1 for r in results if r["status"] == "ok")
    print(f"\n✓ Done. {ok_count}/{len(questions)} answered successfully.")
    print("Run: python3 evals/score.py")


if __name__ == "__main__":
    asyncio.run(run_evals())
