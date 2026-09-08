"""
Lightweight local semantic RAG for AML/policy documents.

Embeddings: sentence-transformers/all-MiniLM-L6-v2, run entirely
locally - no external embedding API is ever called, and the model
is never trained or fine-tuned here.

Vector store: a local FAISS flat inner-product index over
L2-normalized embeddings (mathematically equivalent to cosine
similarity), persisted under data/processed/policy_index/ alongside
a JSON metadata file mapping each vector back to its source policy
filename, chunk id, and chunk text.

TRUST BOUNDARY: this module never calls an LLM and makes no
authorization or business-rule decisions. It only returns policy
text as retrieval evidence. Everything returned here is treated by
the rest of the system as untrusted, quoted evidence for the
report-generation prompt - never as instructions to execute, and
never as a substitute for the deterministic backend authorization
implemented in app/auth/ and app/services/.
"""

import json
from pathlib import Path

import numpy as np
import faiss
from sentence_transformers import SentenceTransformer

POLICY_DIR = Path("data/policies")
INDEX_DIR = Path("data/processed/policy_index")
INDEX_FILE = INDEX_DIR / "index.faiss"
METADATA_FILE = INDEX_DIR / "metadata.json"

MODEL_NAME = "all-MiniLM-L6-v2"

DEFAULT_TOP_K = 5


class PolicyIndexNotFoundError(Exception):
    """
    Raised when semantic search is attempted before the policy
    index has been built on this machine.
    """


# Lazily-initialized, process-wide singletons. Loaded once on first
# use rather than per-request/per-query.
_model: SentenceTransformer | None = None
_index = None
_metadata: list[dict] | None = None


def discover_policy_files() -> list[Path]:
    return sorted(POLICY_DIR.glob("*.txt"))


def chunk_text(text: str) -> list[str]:
    """
    Simple, deterministic paragraph-based chunking: split on blank
    lines. Deliberately unsophisticated - the current policy corpus
    is a handful of short text files, and a paragraph is already a
    meaningful, self-contained unit of policy text. Reproducible:
    the same input always produces the same chunks in the same
    order.
    """
    raw_chunks = text.replace("\r\n", "\n").split("\n\n")

    return [chunk.strip() for chunk in raw_chunks if chunk.strip()]


def get_embedding_model() -> SentenceTransformer:
    global _model

    if _model is None:
        _model = SentenceTransformer(MODEL_NAME)

    return _model


def _embed(texts: list[str]) -> np.ndarray:
    model = get_embedding_model()

    embeddings = model.encode(
        texts,
        convert_to_numpy=True,
        normalize_embeddings=True,
    )

    return np.asarray(embeddings, dtype="float32")


def build_index() -> dict:
    """
    Rebuilds the FAISS index from scratch from data/policies/*.txt
    and persists both the index and its chunk metadata to disk.
    Deterministic given the same source files and embedding model.
    Returns a small summary dict (used by scripts/build_policy_index.py
    and tests).
    """
    policy_files = discover_policy_files()

    metadata: list[dict] = []
    all_chunks: list[str] = []

    for file_path in policy_files:
        text = file_path.read_text(encoding="utf-8")

        for chunk_id, chunk in enumerate(chunk_text(text)):
            metadata.append({
                "policy": file_path.name,
                "chunk_id": chunk_id,
                "content": chunk,
            })
            all_chunks.append(chunk)

    INDEX_DIR.mkdir(parents=True, exist_ok=True)

    model = get_embedding_model()

    if hasattr(model, "get_embedding_dimension"):
        dimension = model.get_embedding_dimension()
    else:
        dimension = model.get_sentence_embedding_dimension()

    index = faiss.IndexFlatIP(dimension)

    if all_chunks:
        embeddings = _embed(all_chunks)
        index.add(embeddings)

    faiss.write_index(index, str(INDEX_FILE))
    METADATA_FILE.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    global _index, _metadata
    _index = index
    _metadata = metadata

    return {
        "policy_files": len(policy_files),
        "chunks": len(all_chunks),
    }


def _load_index() -> None:
    global _index, _metadata

    if _index is not None and _metadata is not None:
        return

    if not INDEX_FILE.exists() or not METADATA_FILE.exists():
        raise PolicyIndexNotFoundError(
            "Policy index not found. Build it first with: "
            "python -m scripts.build_policy_index"
        )

    _index = faiss.read_index(str(INDEX_FILE))
    _metadata = json.loads(METADATA_FILE.read_text(encoding="utf-8"))


def search_policy(query: str, top_k: int = DEFAULT_TOP_K) -> list[dict]:
    """
    Semantic search over the persisted FAISS policy index.

    Returns up to `top_k` results, each:
        {
            "policy": "<source filename>",
            "chunk_id": <int, 0-based, stable for a given index build>,
            "score": <float>,
            "content": "<chunk text>",
        }

    `score` is the cosine similarity (computed as inner-product over
    L2-normalized embeddings) between the query and the chunk, in
    the range [-1, 1] - higher means more semantically related. It
    is a retrieval-relevance signal only: NOT a probability, and NOT
    a compliance/approval confidence score. Retrieval is fully
    deterministic - the same query and index always produce the
    same ranked results.
    """
    _load_index()

    if _index.ntotal == 0:
        return []

    query_embedding = _embed([query])

    k = min(top_k, _index.ntotal)
    scores, indices = _index.search(query_embedding, k)

    results = []

    for score, idx in zip(scores[0], indices[0]):
        if idx == -1:
            continue

        record = _metadata[idx]

        results.append({
            "policy": record["policy"],
            "chunk_id": record["chunk_id"],
            "score": float(score),
            "content": record["content"],
        })

    return results
