from app.rag.policy_rag import search_policy as _semantic_search_policy


def search_policy(query: str, top_k: int = 5) -> list[dict]:
    """
    Retrieve policy chunks relevant to `query` using local semantic
    search (sentence-transformers + FAISS - see app/rag/policy_rag.py).
    Preserves the previous keyword-search tool interface: callers
    that only pass `query` are unaffected.
    """
    return _semantic_search_policy(query, top_k=top_k)
