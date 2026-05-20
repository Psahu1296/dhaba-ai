import asyncio
import json
import sys
import os

# Add project root to sys.path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from tools.bill_app import login
from graph import run_graph


async def run_evals():
    await login()
    print("✓ Logged into Bill-App\n")

    with open("evals/questions.json") as f:
        questions = json.load(f)

    results = []

    for q in questions:
        print(f"[{q['id']}/20] {q['question']}")
        try:
            thread_id = f"eval-{q['id']}"
            answer = await run_graph(q["question"], thread_id=thread_id)
            status = "ok"
        except Exception as e:
            answer = f"ERROR: {e}"
            status = "error"

        results.append({
            "id": q["id"],
            "question": q["question"],
            "expected_topics": q["expected_topics"],
            "answer": answer,
            "status": status,
        })
        print(f"  → {answer[:80]}...\n" if len(answer) > 80 else f"  → {answer}\n")

    with open("evals/results.json", "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    ok_count = sum(1 for r in results if r["status"] == "ok")
    print(f"\n✓ Done. {ok_count}/20 answered successfully.")
    print("Results saved to evals/results.json")


if __name__ == "__main__":
    asyncio.run(run_evals())
