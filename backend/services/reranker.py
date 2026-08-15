"""BGE-reranker fine-rank via sentence-transformers CrossEncoder."""
from sentence_transformers import CrossEncoder
from config import RERANK_MODEL, RERANK_TOP_N
from services import NN_LOCK

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
        # 候选少即全部保留，补满分标记——否则 grade 判 0 分触发无谓改写重试
        for c in candidates:
            c["rerank_score"] = 1.0
        return candidates

    reranker = _get_reranker()
    pairs = [(query, c["text"]) for c in candidates]
    with NN_LOCK:  # GPU 推理串行，防并发 OOM
        scores = reranker.predict(pairs, show_progress_bar=False)

    for c, s in zip(candidates, scores):
        c["rerank_score"] = float(s)
    candidates.sort(key=lambda x: x.get("rerank_score", 0), reverse=True)
    return candidates[:top_n]
