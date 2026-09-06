from pathlib import Path


POLICY_DIR = Path("data/policies")


def search_policy(query: str) -> list[dict]:
    results = []

    query_words = set(query.lower().split())

    for file_path in POLICY_DIR.glob("*.txt"):
        text = file_path.read_text(encoding="utf-8")

        text_words = set(text.lower().split())

        score = len(query_words.intersection(text_words))

        if score > 0:
            results.append({
                "policy": file_path.name,
                "score": score,
                "content": text
            })

    results.sort(
        key=lambda x: x["score"],
        reverse=True
    )

    return results[:5]