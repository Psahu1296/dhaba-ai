import json
import os
import sys

RESULTS_FILE = os.path.join(os.path.dirname(__file__), "results.json")
USE_LLM_JUDGE = "--llm-judge" in sys.argv


def llm_judge(question: str, answer: str) -> tuple[int, str]:
    """LLM-as-judge using GPT-4o-mini. Run with --llm-judge flag. ~$0.001/question."""
    try:
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        prompt = f"""You are evaluating a dhaba (Indian restaurant) AI assistant.
Question: {question}
Answer: {answer}

Score the answer 1-5:
5 = Correct, specific numbers/data, answers exactly what was asked
4 = Mostly correct, minor gaps
3 = Partially answers, missing key data
2 = Vague or mostly wrong
1 = Wrong, hallucinated, or refused to answer

Reply with ONLY: <score>|<one line reason>
Example: 4|Revenue correct but missing peak hours"""
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=60,
            temperature=0,
        )
        raw = resp.choices[0].message.content.strip()
        score, reason = raw.split("|", 1)
        return int(score.strip()), reason.strip()
    except Exception as e:
        return 0, f"llm-judge error: {e}"


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

    # expected_topics in results.json may be stale — always use questions.json
    questions_file = os.path.join(os.path.dirname(__file__), "questions.json")
    if os.path.exists(questions_file):
        with open(questions_file) as f:
            questions = json.load(f)
        topic_map = {q["id"]: q["expected_topics"] for q in questions}
        for r in results:
            if r["id"] in topic_map:
                r["expected_topics"] = topic_map[r["id"]]

    scores = []
    print(f"{'ID':<4} {'Score':<7} {'Question':<45} Reason")
    print("-" * 100)

    for r in results:
        if r["status"] == "error":
            print(f"{r['id']:<4} {'ERROR':<7} {r['question'][:44]:<45}")
            continue

        if USE_LLM_JUDGE:
            score, reason = llm_judge(r["question"], r["answer"])
        else:
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
