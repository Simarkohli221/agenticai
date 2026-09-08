"""
Rebuilds the local semantic policy index from data/policies/*.txt.

Run this once after adding/changing policy documents, or whenever
data/processed/policy_index/ is missing:

    python -m scripts.build_policy_index
"""

from app.rag.policy_rag import build_index


if __name__ == "__main__":
    summary = build_index()

    print("=== Policy Index Build Complete ===")
    print(f"Policy files indexed: {summary['policy_files']}")
    print(f"Chunks embedded: {summary['chunks']}")
