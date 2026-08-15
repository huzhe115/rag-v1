"""ChromaDB vector store + BM25 keyword index. Singleton, loaded once at startup."""
import pickle
import uuid
import jieba
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
from rank_bm25 import BM25Okapi

from config import CHROMA_DIR, BM25_CACHE, EMBED_MODEL, BGE_QUERY_PREFIX


class IndexerService:
    _instance = None

    def __init__(self):
        self.client = chromadb.PersistentClient(
            path=str(CHROMA_DIR),
            settings=Settings(anonymized_telemetry=False),
        )
        self.collection = self.client.get_or_create_collection(
            name="rag_v1",
            metadata={"hnsw:space": "cosine"},
        )
        self.embed_model = SentenceTransformer(EMBED_MODEL)
        self.bm25: BM25Okapi | None = None
        self.bm25_ids: list[str] = []       # parent IDs matching bm25 index order
        self.bm25_texts: list[str] = []      # tokenized parent texts

    @classmethod
    def get_instance(cls) -> "IndexerService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # ---------- public API ----------

    def add_document(self, doc_id: str, filename: str, parent_chunks: list[str],
                     rebuild_bm25: bool = True) -> int:
        """Index all parent chunks (embed) and children (embed). Returns chunk_count."""
        all_ids, all_docs, all_metadatas, all_embeddings = [], [], [], []

        for pi, parent_text in enumerate(parent_chunks):
            parent_id = f"{doc_id}_p{pi}"

            # --- embed parent ---
            all_ids.append(parent_id)
            all_docs.append(parent_text)
            all_metadatas.append({
                "doc_id": doc_id,
                "filename": filename,
                "kind": "parent",
                "idx": pi,
            })

            # --- split children & embed ---
            from services.chunker import split_children
            children = split_children(parent_text)
            child_texts = []
            for ci, child_text in enumerate(children):
                cid = f"{doc_id}_p{pi}_c{ci}"
                all_ids.append(cid)
                child_texts.append(child_text)
                all_metadatas.append({
                    "doc_id": doc_id,
                    "filename": filename,
                    "kind": "child",
                    "parent_id": parent_id,
                    "parent_idx": pi,
                    "idx": ci,
                })
            all_docs.extend(child_texts)

        # batch embed all docs at once
        if all_docs:
            all_embeddings = self.embed_model.encode(
                all_docs, normalize_embeddings=True, show_progress_bar=False
            ).tolist()

        if all_ids:
            self.collection.add(
                ids=all_ids,
                documents=all_docs,
                metadatas=all_metadatas,
                embeddings=all_embeddings,
            )

        if rebuild_bm25:
            self._append_bm25([f"{doc_id}_p{pi}" for pi in range(len(parent_chunks))],
                              parent_chunks)
        return len(parent_chunks)

    def delete_document(self, doc_id: str):
        self.collection.delete(where={"doc_id": doc_id})
        self._remove_bm25(doc_id)

    def load(self):
        """Startup: load BM25 from cache if present, else rebuild from Chroma."""
        if self._load_bm25_cache():
            return
        self.rebuild_bm25()

    # ---------- internal ----------

    def _rebuild_from_parts(self, ids: list[str], texts: list[str]):
        """Recompute BM25Okapi statistics from tokenized corpus and persist to cache."""
        if not ids:
            self.bm25, self.bm25_ids, self.bm25_texts = None, [], []
        else:
            self.bm25 = BM25Okapi(texts)
            self.bm25_ids = ids
            self.bm25_texts = texts
        self._save_bm25_cache()

    def _append_bm25(self, parent_ids: list[str], parent_texts: list[str]):
        """Incremental add: tokenize only the new parents, keep existing entries."""
        new_texts = [list(jieba.cut(t)) for t in parent_texts]
        self._rebuild_from_parts(self.bm25_ids + parent_ids, self.bm25_texts + new_texts)

    def _remove_bm25(self, doc_id: str):
        """Incremental remove: drop entries of one doc, keep the rest."""
        keep = [(i, t) for i, t in zip(self.bm25_ids, self.bm25_texts)
                if not i.startswith(f"{doc_id}_")]
        self._rebuild_from_parts([i for i, _ in keep], [t for _, t in keep])

    def _save_bm25_cache(self):
        try:
            with open(BM25_CACHE, "wb") as f:
                pickle.dump((self.bm25, self.bm25_ids, self.bm25_texts), f)
        except Exception:
            pass  # 缓存写失败不影响服务，下次全量重建

    def _load_bm25_cache(self) -> bool:
        try:
            with open(BM25_CACHE, "rb") as f:
                self.bm25, self.bm25_ids, self.bm25_texts = pickle.load(f)
            return True
        except Exception:
            return False

    def rebuild_bm25(self):
        """Full rebuild from Chroma (cache miss / import fallback)."""
        try:
            result = self.collection.get(where={"kind": "parent"})
        except Exception:
            result = None

        if not result or not result["ids"]:
            self._rebuild_from_parts([], [])
            return

        # jieba tokenize for Chinese BM25
        tokenized = [list(jieba.cut(doc)) for doc in result["documents"]]
        self._rebuild_from_parts(result["ids"], tokenized)

    # ---------- retrieval helpers ----------

    def embed_query(self, query: str) -> list[float]:
        return self.embed_model.encode(
            BGE_QUERY_PREFIX + query, normalize_embeddings=True
        ).tolist()

    def vector_search(self, qvec: list[float], k: int) -> list[str]:
        """Return parent IDs from vector search over children, deduped."""
        results = self.collection.query(
            query_embeddings=[qvec],
            n_results=k,
            where={"kind": "child"},
        )
        seen = set()
        parent_ids = []
        for meta in results["metadatas"][0]:
            pid = meta.get("parent_id")  # always present for children
            if pid and pid not in seen:
                seen.add(pid)
                parent_ids.append(pid)
        return parent_ids

    def bm25_search(self, query: str, k: int) -> list[str]:
        """Return parent IDs from BM25 search."""
        if self.bm25 is None:
            return []
        tokens = list(jieba.cut(query))
        scores = self.bm25.get_scores(tokens)
        # get top-k indices
        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)[:k]
        return [self.bm25_ids[i] for i, _ in ranked if scores[i] > 0]

    def get_parents(self, parent_ids: list[str]) -> list[dict]:
        """Fetch parent docs by IDs. Returns [{id, text, filename}, ...] in order."""
        if not parent_ids:
            return []
        result = self.collection.get(ids=parent_ids)
        # map back to preserve input order
        id_to_doc = {
            rid: {"id": rid, "text": doc, "filename": meta.get("filename", "")}
            for rid, doc, meta in zip(result["ids"], result["documents"], result["metadatas"])
        }
        return [id_to_doc[pid] for pid in parent_ids if pid in id_to_doc]
