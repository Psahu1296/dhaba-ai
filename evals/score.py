import json
import os

RESULTS_FILE = os.path.join(os.path.dirname(__file__), "results.json")


def judge(_question: str, expected_topics: list, answer: str) -> tuple[int, str]:
    """Keyword-based scorer — no LLM needed. Fast, deterministic."""
    if not answer or not answer.strip():
        return 1, "empty answer"

    answer_lower = answer.lower()
    matched = [t for t in expected_topics if t.lower() in answer_lower]
    coverage = len(matched) / len(expected_topics) if expected_topics else 1.0

    if coverage >= 1.0:
        score = 5
        reason = f"all {len(expected_topics)} topics covered"
    elif coverage >= 0.75:
        score = 4
        reason = f"{len(matched)}/{len(expected_topics)} topics covered"
    elif coverage >= 0.5:
        score = 3
        reason = f"{len(matched)}/{len(expected_topics)} topics covered — missing: {[t for t in expected_topics if t.lower() not in answer_lower]}"
    elif coverage >= 0.25:
        score = 2
        reason = f"only {len(matched)}/{len(expected_topics)} topics found"
    else:
        score = 1
        reason = f"0/{len(expected_topics)} expected topics in answer"

    return score, reason


def run_scoring():
    with open("evals/results.json") as f:
        results = json.load(f)

    scores = []
    print(f"{'ID':<4} {'Score':<7} {'Question':<45} Reason")
    print("-" * 100)

    for r in results:
        if r["status"] == "error":
            print(f"{r['id']:<4} {'ERROR':<7} {r['question'][:44]:<45}")
            continue

        score, reason = judge(r["question"], r["expected_topics"], r["answer"])
        scores.append(score)
        stars = "★" * score + "☆" * (5 - score)
        print(f"{r['id']:<4} {stars} {r['question'][:44]:<45} {reason[:50]}")

    if scores:
        avg = sum(scores) / len(scores)
        print(f"\n{'─' * 100}")
        print(f"Average score: {avg:.1f}/5.0  ({len(scores)} questions scored)")
        print(f"Pass (≥3.5): {'✅ YES' if avg >= 3.5 else '❌ NO'}")


if __name__ == "__main__":
    run_scoring()
