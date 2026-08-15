import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import FileDrop from "../components/FileDrop";
import { getDocuments, deleteDocument, uploadFiles } from "../api";
import type { DocRecord, UploadResult } from "../types";

function fmtSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export default function UploadPage() {
  const [docs, setDocs] = useState<DocRecord[]>([]);
  const [uploading, setUploading] = useState(false);
  const [toasts, setToasts] = useState<UploadResult[]>([]);
  const navigate = useNavigate();

  const loadDocs = useCallback(async () => {
    try {
      setDocs(await getDocuments());
    } catch { /* ignore */ }
  }, []);

  useEffect(() => { loadDocs(); }, [loadDocs]);

  const handleUpload = async (files: File[]) => {
    setUploading(true);
    const results = await uploadFiles(files);
    setToasts(results);
    await loadDocs();
    setUploading(false);
    setTimeout(() => setToasts([]), 5000);
  };

  const handleDelete = async (id: string) => {
    await deleteDocument(id);
    setDocs((prev) => prev.filter((d) => d.id !== id));
  };

  return (
    <div className="page">
      <header className="page-header">
        <h1>RAG 知识库</h1>
        <p>上传文档，构建你的私有知识库，然后向它提问</p>
      </header>

      <FileDrop onUpload={handleUpload} uploading={uploading} />

      {toasts.length > 0 && (
        <div className="toast-container">
          {toasts.map((t, i) => (
            <div key={i} className={`toast toast-${t.status}`}>
              {t.status === "ok" && `✅ ${t.filename} 上传成功 (${t.chunk_count} 块)`}
              {t.status === "duplicate" && `⚠️ ${t.message}`}
              {t.status === "error" && `❌ ${t.filename}: ${t.message}`}
            </div>
          ))}
        </div>
      )}

      <section className="doc-list">
        <h2>已上传文档 ({docs.length})</h2>
        {docs.length === 0 ? (
          <p className="empty-hint">还没上传任何文档</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>文件名</th>
                <th>大小</th>
                <th>分块数</th>
                <th>上传时间</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {docs.map((d) => (
                <tr key={d.id}>
                  <td>{d.filename}</td>
                  <td>{fmtSize(d.size)}</td>
                  <td>{d.chunk_count}</td>
                  <td>{new Date(d.created_at).toLocaleString("zh-CN")}</td>
                  <td>
                    <button className="btn-danger" onClick={() => handleDelete(d.id)}>
                      删除
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <div style={{ marginTop: 24 }}>
        <button className="btn-primary" onClick={() => navigate("/chat")}>
          去提问 →
        </button>
      </div>
    </div>
  );
}
