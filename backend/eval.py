"""检索链路评测：Hit@k + MRR@5，四档消融对比。

用法：cd backend && python eval.py

评测集见 eval_qa.json。命中判定：检索返回的父块文本中
是否包含该问题的答案段落（原文摘录，忽略空白差异）。
"""
import json
import re
from pathlib import Path

from services.indexer import IndexerService
from services.retriever import retrieve
from services.reranker import rerank

K_VALS = (1, 3, 5)


def norm(s: str) -> str:
    return re.sub(r"\s+", "", s)


def load_qa() -> list[dict]:
    with open(Path(__file__).parent / "eval_qa.json", encoding="utf-8") as f:
        return json.load(f)


def find_rank(docs: list[dict], answers: list[str]) -> int:
    """第一个包含答案段落的文档排名（1-based），未命中返回 0。"""
    for i, d in enumerate(docs, 1):
        text = norm(d["text"])
        if any(norm(a) in text for a in answers):
            return i
    return 0


def evaluate(qa_pairs: list[dict], get_ranked) -> tuple[dict, list[tuple]]:
    hits = {k: 0 for k in K_VALS}
    mrr5 = 0.0
    ranks = []
    for qa in qa_pairs:
        rank = find_rank(get_ranked(qa["question"]), qa["answers"])
        ranks.append((qa, rank))
        for k in K_VALS:
            if 0 < rank <= k:
                hits[k] += 1
        if 0 < rank <= 5:
            mrr5 += 1.0 / rank
    n = len(qa_pairs)
    metrics = {f"hit@{k}": hits[k] / n for k in K_VALS} | {"mrr@5": mrr5 / n}
    return metrics, ranks


def main():
    qa_pairs = load_qa()
    idx = IndexerService.get_instance()
    idx.load()

    def stage_vector(q):
        return idx.get_parents(idx.vector_search(idx.embed_query(q), 8))

    def stage_bm25(q):
        return idx.get_parents(idx.bm25_search(q, 8))

    def stage_fused(q):
        return retrieve(q, top_n=20)

    def stage_rerank(q):
        return rerank(q, retrieve(q, top_n=20))

    parents = idx.collection.get(where={"kind": "parent"})
    print(f"语料父块数: {len(parents['ids'])}, 评测问题数: {len(qa_pairs)}\n")

    print(f"{'方法':<14}{'Hit@1':>8}{'Hit@3':>8}{'Hit@5':>8}{'MRR@5':>8}")
    rerank_ranks = None
    for name, fn in [("仅向量", stage_vector), ("仅BM25", stage_bm25),
                     ("融合(RRF)", stage_fused), ("融合+rerank", stage_rerank)]:
        r, ranks = evaluate(qa_pairs, fn)
        if name == "融合+rerank":
            rerank_ranks = ranks
        print(f"{name:<14}{r['hit@1']:>7.1%}{r['hit@3']:>7.1%}"
              f"{r['hit@5']:>7.1%}{r['mrr@5']:>8.3f}")

    misses = [(qa["question"], qa["doc"], rank) for qa, rank in rerank_ranks
              if rank == 0 or rank > 5]
    if misses:
        print("\n最终链路（融合+rerank Top-5）未命中：")
        for q, doc, rank in misses:
            print(f"  - [{doc}] {q} (实际命中排名: {rank or '无'})")


if __name__ == "__main__":
    main()
