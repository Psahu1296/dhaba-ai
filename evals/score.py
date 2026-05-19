import json
import sys
import os
from openai import OpenAI

# Add project root to sys.path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config import OPENAI_BASE_URL

_client = OpenAI(base_url=OPENAI_BASE_URL, api_key="ollama")

JUDGE_PROMPT = """You are evaluating an AI assistant for a dhaba (Indian restaurant).

Question: {question}
Expected topics to cover: {expected_topics}
Actual answer: {answer}

Score this answer from 1 to 5:
5 - Perfect: accurate, covers expected topics, helpful
4 - Good: mostly accurate, covers most topics
3 - Okay: partially correct, missing some key info
2 - Poor: vague or incomplete
1 - Wrong: incorrect or didn't answer

Reply with ONLY a single number (1-5) and one sentence reason.
Format: SCORE: <number> | REASON: <reason>"""


def judge(question: str, expected_topics: list, answer: str) -> tuple[int, str]:
    prompt = JUDGE_PROMPT.format(
        question=question,
        expected_topics=", ".join(expected_topics),
        answer=answer,
    )
    response = _client.chat.completions.create(
        model="hermes-fast",
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
    )
    text = response.choices[0].message.content.strip()
    try:
        score_part = text.split("|")[0].strip()
        score = int(score_part.replace("SCORE:", "").strip())
        reason = text.split("|")[1].replace("REASON:", "").strip() if "|" in text else ""
        return max(1, min(5, score)), reason
    except Exception:
        return 3, text


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
