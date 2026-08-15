"""SQLite database — sessions, messages, documents. Zero config."""
import sqlite3
import uuid
from datetime import datetime, timezone
from config import DB_PATH


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _conn():
    c = sqlite3.connect(str(DB_PATH))
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA foreign_keys=ON")
    return c


def init_db():
    with _conn() as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL DEFAULT '新对话',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                path TEXT NOT NULL,
                size INTEGER NOT NULL,
                content_hash TEXT NOT NULL,
                chunk_count INTEGER NOT NULL,
                created_at TEXT NOT NULL
            );
        """)


# --- Sessions ---

def create_session(title: str = "新对话") -> dict:
    sid = uuid.uuid4().hex[:12]
    now = _utcnow()
    with _conn() as db:
        db.execute(
            "INSERT INTO sessions (id, title, created_at, updated_at) VALUES (?,?,?,?)",
            (sid, title, now, now),
        )
    return {"id": sid, "title": title, "created_at": now, "updated_at": now}


def list_sessions() -> list[dict]:
    with _conn() as db:
        rows = db.execute(
            "SELECT id, title, created_at, updated_at FROM sessions ORDER BY updated_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def get_session(sid: str) -> dict | None:
    with _conn() as db:
        r = db.execute(
            "SELECT id, title, created_at, updated_at FROM sessions WHERE id=?", (sid,)
        ).fetchone()
    return dict(r) if r else None


def update_session(sid: str, *, title: str | None = None):
    now = _utcnow()
    with _conn() as db:
        if title:
            db.execute(
                "UPDATE sessions SET title=?, updated_at=? WHERE id=?",
                (title, now, sid),
            )
        else:
            db.execute(
                "UPDATE sessions SET updated_at=? WHERE id=?", (now, sid)
            )


def delete_session(sid: str):
    with _conn() as db:
        db.execute("DELETE FROM messages WHERE session_id=?", (sid,))
        db.execute("DELETE FROM sessions WHERE id=?", (sid,))


# --- Messages ---

def add_message(sid: str, role: str, content: str) -> int:
    now = _utcnow()
    with _conn() as db:
        cur = db.execute(
            "INSERT INTO messages (session_id, role, content, created_at) VALUES (?,?,?,?)",
            (sid, role, content, now),
        )
        return cur.lastrowid


def get_messages(sid: str, limit: int = 50) -> list[dict]:
    with _conn() as db:
        rows = db.execute(
            "SELECT id, session_id, role, content, created_at FROM messages "
            "WHERE session_id=? ORDER BY id ASC LIMIT ?",
            (sid, limit),
        ).fetchall()
    return [dict(r) for r in rows]


# --- Documents ---

def insert_document(doc_id: str, filename: str, path: str, size: int,
                    content_hash: str, chunk_count: int) -> dict:
    now = _utcnow()
    with _conn() as db:
        db.execute(
            "INSERT INTO documents (id, filename, path, size, content_hash, chunk_count, created_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (doc_id, filename, path, size, content_hash, chunk_count, now),
        )
    return {"id": doc_id, "filename": filename, "size": size,
            "chunk_count": chunk_count, "created_at": now}


def get_document_by_hash(content_hash: str) -> dict | None:
    with _conn() as db:
        r = db.execute(
            "SELECT id, filename, path, size, content_hash, chunk_count, created_at "
            "FROM documents WHERE content_hash=?",
            (content_hash,),
        ).fetchone()
    return dict(r) if r else None


def get_document(doc_id: str) -> dict | None:
    with _conn() as db:
        r = db.execute(
            "SELECT id, filename, path, size, content_hash, chunk_count, created_at "
            "FROM documents WHERE id=?",
            (doc_id,),
        ).fetchone()
    return dict(r) if r else None


def list_documents() -> list[dict]:
    with _conn() as db:
        rows = db.execute(
            "SELECT id, filename, path, size, chunk_count, created_at "
            "FROM documents ORDER BY created_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def delete_document(doc_id: str) -> bool:
    with _conn() as db:
        cur = db.execute("DELETE FROM documents WHERE id=?", (doc_id,))
        return cur.rowcount > 0
