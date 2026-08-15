"""批量导入 data/ 下的文档到知识库（与 /api/upload 同一链路 + SHA256 去重）。

用法：cd backend && python import_data.py
"""
import hashlib
import uuid
from pathlib import Path

from config import DOCS_DIR
from models.database import insert_document, get_document_by_hash
from services.parser import parse_file
from services.cleaner import clean_text
from services.chunker import split_parents
from services.indexer import IndexerService

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SUPPORTED = (".pdf", ".txt", ".docx")


def main():
    files = sorted(f for f in DATA_DIR.iterdir() if f.suffix.lower() in SUPPORTED)
    if not files:
        print("data/ 下没有可导入的文件")
        return

    idx = IndexerService.get_instance()
    idx.load()
    for f in files:
        content = f.read_bytes()
        content_hash = hashlib.sha256(content).hexdigest()
        if get_document_by_hash(content_hash):
            print(f"跳过（已存在）: {f.name}")
            continue

        doc_id = uuid.uuid4().hex[:12]
        save_path = DOCS_DIR / f"{doc_id}{f.suffix.lower()}"
        save_path.write_bytes(content)
        text = clean_text(parse_file(save_path))
        parents = split_parents(text)
        chunk_count = idx.add_document(doc_id, f.name, parents, rebuild_bm25=False)
        insert_document(doc_id, f.name, str(save_path), len(content),
                        content_hash, chunk_count)
        print(f"导入: {f.name} ({len(content) // 1024}KB, {chunk_count} 块)")

    idx.rebuild_bm25()  # 批量导入只重建一次

    parents = idx.collection.get(where={"kind": "parent"})
    print(f"\n完成，当前语料父块总数: {len(parents['ids'])}")


if __name__ == "__main__":
    main()
