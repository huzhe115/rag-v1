"""Document upload / list / delete router."""
import asyncio
import hashlib
import uuid
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException
from config import DOCS_DIR, MAX_UPLOAD_MB
from models.database import (insert_document, list_documents, delete_document,
                             get_document, get_document_by_hash)
from services.parser import parse_file
from services.cleaner import clean_text
from services.chunker import split_parents
from services.indexer import IndexerService

router = APIRouter()

MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024


def _process_file(save_path: Path) -> tuple[str, list[str]]:
    """Parse + clean + chunk in a worker thread (CPU-heavy, keep out of event loop)."""
    text = clean_text(parse_file(save_path))
    return text, split_parents(text)


@router.post("/upload")
async def upload(files: list[UploadFile] = File(...)):
    results = []
    idx = IndexerService.get_instance()
    added = False

    for f in files:
        if not f.filename:
            continue

        suffix = Path(f.filename).suffix.lower()
        if suffix not in (".pdf", ".txt", ".docx"):
            results.append({"filename": f.filename, "status": "error",
                            "message": f"不支持的文件格式: {suffix}"})
            continue

        # 大小限制（f.size 可能为 None，读后兜底再查一次）
        if f.size and f.size > MAX_UPLOAD_BYTES:
            results.append({"filename": f.filename, "status": "error",
                            "message": f"文件超过 {MAX_UPLOAD_MB}MB 上限"})
            continue
        content = await f.read()
        if len(content) > MAX_UPLOAD_BYTES:
            results.append({"filename": f.filename, "status": "error",
                            "message": f"文件超过 {MAX_UPLOAD_MB}MB 上限"})
            continue

        # SHA256 dedup
        content_hash = hashlib.sha256(content).hexdigest()
        existing = get_document_by_hash(content_hash)
        if existing:
            results.append({"filename": f.filename, "status": "duplicate",
                            "message": f"文档已存在: {existing['filename']}"})
            continue

        doc_id = uuid.uuid4().hex[:12]
        save_path = DOCS_DIR / f"{doc_id}{suffix}"

        try:
            await asyncio.to_thread(save_path.write_bytes, content)
            text, parents = await asyncio.to_thread(_process_file, save_path)
            chunk_count = await asyncio.to_thread(
                idx.add_document, doc_id, f.filename, parents, rebuild_bm25=False)
            record = await asyncio.to_thread(
                insert_document, doc_id, f.filename, str(save_path),
                len(content), content_hash, chunk_count)
            results.append({**record, "status": "ok"})
            added = True
        except ValueError as e:
            results.append({"filename": f.filename, "status": "error", "message": str(e)})
            if save_path.exists():
                save_path.unlink()
        except Exception as e:
            # 半索引态回滚：向量可能已入库但 DB 没记录，删干净不留孤儿
            results.append({"filename": f.filename, "status": "error", "message": str(e)})
            try:
                idx.collection.delete(where={"doc_id": doc_id})
            except Exception:
                pass
            if save_path.exists():
                save_path.unlink()

    if added:
        await asyncio.to_thread(idx.rebuild_bm25)  # 批量上传只重建一次
    return results


@router.get("/documents")
def list_docs():
    return list_documents()


@router.delete("/documents/{doc_id}")
def delete_doc(doc_id: str):
    record = get_document(doc_id)
    if not record:
        raise HTTPException(404, "文档不存在")
    IndexerService.get_instance().delete_document(doc_id)
    delete_document(doc_id)
    try:
        Path(record["path"]).unlink(missing_ok=True)
    except OSError:
        pass  # 文件已不在或无法删除不影响接口结果
    return {"ok": True}
