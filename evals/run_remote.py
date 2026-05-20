import asyncio
import json
import sys
import os
import httpx

BASE_URL = os.getenv("EVAL_API_BASE", "https://dhaba-ai-production.up.railway.app")
API_KEY = os.getenv("EVAL_API_KEY", "3e263b3904fb1a7def01b56860ce66369ad73bc04898eb545f295de0a1717297")

QUESTIONS_FILE = os.path.join(os.path.dirname(__file__), "questions.json")
RESULTS_FILE = os.path.join(os.path.dirname(__file__), "results.json")


async def ask(client: httpx.AsyncClient, question: str, q_id: int) -> str:
    response = await client.post(
        "/agent/chat",
        json={"message": question},
        headers={"X-API-Key": API_KEY},
        timeout=60.0,
    )
    response.raise_for_status()
    return response.json().get("answer", "")


async def run_evals():
    with open(QUESTIONS_FILE) as f:
        questions = json.load(f)

    results = []

    async with httpx.AsyncClient(base_url=BASE_URL) as client:
        # Smoke test
        try:
            health = await client.get("/", timeout=10.0)
            print(f"✓ API reachable: {BASE_URL} ({health.status_code})\n")
        except Exception as e:
            print(f"✗ Cannot reach API: {e}")
            sys.exit(1)

        for q in questions:
            print(f"[{q['id']:2}/20] {q['question']}")
            try:
                answer = await ask(client, q["question"], q["id"])
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
            preview = answer[:80] + "..." if len(answer) > 80 else answer
            print(f"       → {preview}\n")

    with open(RESULTS_FILE, "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    ok = sum(1 for r in results if r["status"] == "ok")
    empty = sum(1 for r in results if r.get("answer", "").strip() == "")
    errors = sum(1 for r in results if r["status"] == "error")
    print(f"✓ Done. {ok}/20 answered | {empty} empty | {errors} errors")
    print(f"Results saved to evals/results.json")


if __name__ == "__main__":
    asyncio.run(run_evals())
