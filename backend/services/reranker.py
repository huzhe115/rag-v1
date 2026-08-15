"""BGE-reranker fine-rank via sentence-transformers CrossEncoder."""
from sentence_transformers import CrossEncoder
from config import RERANK_MODEL, RERANK_TOP_N

_reranker: CrossEncoder | None = None


def _get_reranker() -> CrossEncoder:
    global _reranker
    if _reranker is None:
        _reranker = CrossEncoder(RERANK_MODEL)
    return _reranker


def rerank(query: str, candidates: list[dict], top_n: int = RERANK_TOP_N) -> list[dict]:
    """Score candidates with BGE-reranker, return top_n sorted by score desc."""
    if not candidates:
        return []
    if len(candidates) <= top_n:
        return candidates

    reranker = _get_reranker()
    pairs = [(query, c["text"]) for c in candidates]
    scores = reranker.predict(pairs, show_progress_bar=False)

    for c, s in zip(candidates, scores):
        c["rerank_score"] = float(s)
    candidates.sort(key=lambda x: x.get("rerank_score", 0), reverse=True)
    return candidates[:top_n]
