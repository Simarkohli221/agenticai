"""
Tests Step 11 semantic policy RAG.

Retrieval tests (1-14) never call Groq/the LLM - they only exercise
app/rag/policy_rag.py directly, so they are fast, free, and
deterministic. Workflow tests (15-17) run the real investigation
graph once (one Groq call for parsing, one for report generation on
a LOW-risk account) to prove the semantic RAG output is correctly
threaded through to the final report with traceable citations.
"""

import json
import shutil

import numpy as np

import app.rag.policy_rag as policy_rag
from app.rag.policy_rag import (
    build_index,
    discover_policy_files,
    chunk_text,
    get_embedding_model,
    search_policy,
    PolicyIndexNotFoundError,
    INDEX_FILE,
    METADATA_FILE,
    INDEX_DIR,
)
from app.tools.policy_tool import search_policy as tool_search_policy

RELATED_QUERY = "human review high risk escalation of suspicious activity"
UNRELATED_QUERY = "pizza recipe ingredients and cooking instructions"

# A related query's top score should clearly exceed this; an
# unrelated query's top score should clearly fall below it. This is
# a coarse sanity threshold, not a compliance/probability cutoff.
RELEVANCE_THRESHOLD = 0.3


def result_label(passed: bool) -> str:
    return "PASS" if passed else "FAIL"


if __name__ == "__main__":
    print("=== Retrieval tests (no LLM) ===")

    # 1. Index builds successfully
    summary = build_index()
    test1_passed = summary["policy_files"] >= 1 and summary["chunks"] >= 1
    print("Index builds successfully:", result_label(test1_passed))

    # 2. Policy files are discovered
    files = discover_policy_files()
    test2_passed = len(files) >= 1 and any(
        f.name == "aml_policy.txt" for f in files
    )
    print("Policy files discovered:", result_label(test2_passed))

    # 3. Chunks are created
    sample_text = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
    sample_chunks = chunk_text(sample_text)
    test3_passed = sample_chunks == [
        "First paragraph.",
        "Second paragraph.",
        "Third paragraph.",
    ]
    print("Chunks are created:", result_label(test3_passed))

    # 4. Embeddings are generated
    model = get_embedding_model()
    embedding = model.encode(["test sentence"], normalize_embeddings=True)
    test4_passed = (
        isinstance(embedding, np.ndarray)
        and embedding.shape[0] == 1
        and embedding.shape[1] > 0
    )
    print("Embeddings are generated:", result_label(test4_passed))

    # 5. FAISS index is created (persisted to disk)
    test5_passed = INDEX_FILE.exists() and METADATA_FILE.exists()
    print("FAISS index is created:", result_label(test5_passed))

    # 6. Semantic search returns results
    related_results = search_policy(RELATED_QUERY, top_k=5)
    test6_passed = len(related_results) > 0
    print("Semantic search returns results:", result_label(test6_passed))

    # 7-10. Result shape
    first = related_results[0]
    test7_passed = first.get("policy") == "aml_policy.txt"
    test8_passed = isinstance(first.get("chunk_id"), int)
    test9_passed = isinstance(first.get("score"), float)
    test10_passed = isinstance(first.get("content"), str) and len(first["content"]) > 0
    print("Result contains policy filename:", result_label(test7_passed))
    print("Result contains chunk ID:", result_label(test8_passed))
    print("Result contains similarity score:", result_label(test9_passed))
    print("Result contains source content:", result_label(test10_passed))

    # 11. Semantically related query retrieves AML policy with a
    # meaningfully high score
    test11_passed = (
        related_results[0]["policy"] == "aml_policy.txt"
        and related_results[0]["score"] > RELEVANCE_THRESHOLD
    )
    print(
        "Related query retrieves AML policy with high score:",
        result_label(test11_passed),
    )

    # 12. Unrelated query does not incorrectly claim policy support
    unrelated_results = search_policy(UNRELATED_QUERY, top_k=5)
    test12_passed = (
        len(unrelated_results) == 0
        or unrelated_results[0]["score"] < RELEVANCE_THRESHOLD
    )
    print(
        "Unrelated query does not claim policy support:",
        result_label(test12_passed),
    )

    # 13. top_k is respected
    limited_results = search_policy(RELATED_QUERY, top_k=2)
    test13_passed = len(limited_results) <= 2
    print("top_k is respected:", result_label(test13_passed))

    # 14. Missing index produces a clear error
    backup_dir = INDEX_DIR.parent / "policy_index_backup_for_test"
    shutil.move(str(INDEX_DIR), str(backup_dir))
    policy_rag._index = None
    policy_rag._metadata = None

    try:
        search_policy(RELATED_QUERY)
        test14_passed = False
    except PolicyIndexNotFoundError:
        test14_passed = True
    finally:
        shutil.move(str(backup_dir), str(INDEX_DIR))
        policy_rag._index = None
        policy_rag._metadata = None

    print("Missing index produces a clear error:", result_label(test14_passed))

    # Confirm the tool-layer interface still works after the reload.
    tool_results = tool_search_policy(RELATED_QUERY)
    tool_interface_ok = len(tool_results) > 0
    print("Tool-layer interface still functions:", result_label(tool_interface_ok))

    print()
    print("=== Investigation workflow tests (uses Groq) ===")

    from app.agent.graph import investigation_graph
    import uuid

    config = {"configurable": {"thread_id": f"policy-rag-test-{uuid.uuid4()}"}}
    result = investigation_graph.invoke(
        {"user_request": "Investigate account 8000EBD30 for suspicious activity."},
        config=config,
    )

    report = result.get("investigation_report", {})

    # 15. Existing investigation workflow still works
    test15_passed = (
        report.get("status") != "ERROR"
        and "llm_summary" in report
    )
    print("Existing investigation workflow still works:", result_label(test15_passed))

    # 16. Generated report includes policy evidence/citation
    policy_evidence = report.get("policy_evidence", [])
    policy_citations = report.get("policy_citations", [])
    test16_passed = (
        "policy_evidence_found" in report
        and len(policy_evidence) > 0
        and len(policy_citations) > 0
        and all(
            " (chunk " in citation and citation.endswith(")")
            for citation in policy_citations
        )
    )
    print(
        "Report includes policy evidence/citation:",
        result_label(test16_passed),
    )

    # 17. No fabricated policy text: every piece of evidence in the
    # report must be traceable to a real (policy, chunk_id, content)
    # entry actually persisted in the index metadata.
    persisted_metadata = json.loads(METADATA_FILE.read_text(encoding="utf-8"))
    persisted_lookup = {
        (entry["policy"], entry["chunk_id"]): entry["content"]
        for entry in persisted_metadata
    }

    test17_passed = len(policy_evidence) > 0 and all(
        persisted_lookup.get((item["policy"], item["chunk_id"])) == item["excerpt"]
        for item in policy_evidence
    )
    print(
        "No fabricated policy text (evidence traceable to index):",
        result_label(test17_passed),
    )
