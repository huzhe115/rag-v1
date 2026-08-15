"""Hybrid retrieval: vector + BM25 → RRF fusion → candidate set."""
from config import VECTOR_K, BM25_K, RRF_K
from services.indexer import IndexerService


def retrieve(query: str, top_n: int = 20) -> list[dict]:
    """
    Vector search (k=VECTOR_K) + BM25 search (k=BM25_K) → RRF fusion → top_n candidates.
    Returns [{id, text, filename, score}, ...] sorted by RRF score desc.
    """
    idx = IndexerService.get_instance()

    # 1. Vector search over children → parent IDs
    qvec = idx.embed_query(query)
    vec_pids = idx.vector_search(qvec, VECTOR_K)

    # 2. BM25 search over parents → parent IDs
    bm25_pids = idx.bm25_search(query, BM25_K)

    # 3. RRF fusion
    rrf_scores: dict[str, float] = {}
    for rank, pid in enumerate(vec_pids):
        rrf_scores[pid] = rrf_scores.get(pid, 0) + 1.0 / (RRF_K + rank + 1)
    for rank, pid in enumerate(bm25_pids):
        rrf_scores[pid] = rrf_scores.get(pid, 0) + 1.0 / (RRF_K + rank + 1)

    sorted_pids = sorted(rrf_scores.keys(), key=lambda p: rrf_scores[p], reverse=True)[:top_n]

    # 4. Fetch parent docs
    parents = idx.get_parents(sorted_pids)
    for p in parents:
        p["score"] = rrf_scores.get(p["id"], 0.0)

    return parents
