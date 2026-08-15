"""BM25 cache smoke test: load → append → remove → reload, assert consistency."""
from services.indexer import IndexerService

idx = IndexerService.get_instance()
idx.load()
n = len(idx.bm25_ids)
assert n > 0, "corpus should not be empty"

# incremental append of a fake doc
idx._append_bm25(["__test_p0"], ["数据中台建设方案测试文档"])
assert len(idx.bm25_ids) == n + 1
assert idx.bm25_search("数据中台", 3), "new parent should be searchable"

# incremental remove
idx._remove_bm25("__test")
assert len(idx.bm25_ids) == n

# cache reload must match in-memory state
snapshot = list(idx.bm25_ids)
idx._load_bm25_cache()
assert idx.bm25_ids == snapshot
print(f"ok: {n} parents, append/remove/cache all consistent")
