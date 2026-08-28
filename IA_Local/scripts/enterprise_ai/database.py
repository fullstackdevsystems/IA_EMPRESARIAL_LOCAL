from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


SCHEMA = r"""
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS memories (
    id TEXT PRIMARY KEY,
    company_id TEXT NOT NULL,
    user_id TEXT,
    scope TEXT NOT NULL DEFAULT 'company',
    category TEXT NOT NULL,
    content TEXT NOT NULL,
    source_type TEXT,
    source_ref TEXT,
    confidence REAL NOT NULL DEFAULT 0.7,
    importance REAL NOT NULL DEFAULT 0.5,
    tags_json TEXT NOT NULL DEFAULT '[]',
    sensitivity TEXT NOT NULL DEFAULT 'normal',
    status TEXT NOT NULL DEFAULT 'active',
    active INTEGER NOT NULL DEFAULT 1,
    expires_at TEXT,
    version INTEGER NOT NULL DEFAULT 1,
    supersedes_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_memories_scope ON memories(company_id,user_id,active,status);
CREATE INDEX IF NOT EXISTS idx_memories_category ON memories(company_id,category,active);
CREATE TABLE IF NOT EXISTS memory_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    memory_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    snapshot_json TEXT NOT NULL,
    changed_by TEXT,
    changed_at TEXT NOT NULL,
    reason TEXT,
    FOREIGN KEY(memory_id) REFERENCES memories(id)
);
CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    company_id TEXT NOT NULL,
    user_id TEXT,
    scope TEXT NOT NULL DEFAULT 'company',
    name TEXT NOT NULL,
    stored_path TEXT NOT NULL,
    extension TEXT NOT NULL,
    mime_type TEXT,
    size_bytes INTEGER NOT NULL,
    current_hash TEXT NOT NULL,
    current_version INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'ready',
    active INTEGER NOT NULL DEFAULT 1,
    added_by TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(company_id, scope, user_id, name)
);
CREATE INDEX IF NOT EXISTS idx_documents_scope ON documents(company_id,user_id,active);
CREATE TABLE IF NOT EXISTS document_versions (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    file_hash TEXT NOT NULL,
    stored_path TEXT NOT NULL,
    indexed_at TEXT NOT NULL,
    chunk_count INTEGER NOT NULL DEFAULT 0,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY(document_id) REFERENCES documents(id),
    UNIQUE(document_id, version)
);
CREATE TABLE IF NOT EXISTS document_chunks (
    id TEXT PRIMARY KEY,
    vector_id TEXT NOT NULL,
    document_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    ordinal INTEGER NOT NULL,
    text_hash TEXT NOT NULL,
    content TEXT NOT NULL,
    page INTEGER,
    sheet TEXT,
    section TEXT,
    row_range TEXT,
    injection_flag INTEGER NOT NULL DEFAULT 0,
    active INTEGER NOT NULL DEFAULT 1,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    FOREIGN KEY(document_id) REFERENCES documents(id)
);
CREATE INDEX IF NOT EXISTS idx_chunks_document ON document_chunks(document_id,active,version);
CREATE INDEX IF NOT EXISTS idx_chunks_vector ON document_chunks(vector_id,active);
CREATE TABLE IF NOT EXISTS datasets (
    id TEXT PRIMARY KEY,
    company_id TEXT NOT NULL,
    user_id TEXT,
    scope TEXT NOT NULL DEFAULT 'company',
    name TEXT NOT NULL,
    path TEXT NOT NULL,
    file_hash TEXT,
    sheet TEXT,
    columns_json TEXT NOT NULL DEFAULT '[]',
    roles_json TEXT NOT NULL DEFAULT '{}',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_datasets_scope ON datasets(company_id,user_id,active);
CREATE TABLE IF NOT EXISTS audit_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    company_id TEXT,
    user_id TEXT,
    event_type TEXT NOT NULL,
    object_type TEXT,
    object_id TEXT,
    outcome TEXT NOT NULL DEFAULT 'ok',
    details_json TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_audit_scope ON audit_events(company_id,user_id,timestamp);
CREATE TABLE IF NOT EXISTS query_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    company_id TEXT,
    user_id TEXT,
    prompt_hash TEXT,
    prompt_length INTEGER,
    provider TEXT,
    model TEXT,
    total_ms REAL,
    memory_ms REAL,
    rag_ms REAL,
    structured_ms REAL,
    llm_ms REAL,
    memories_count INTEGER,
    chunks_count INTEGER,
    sources_count INTEGER,
    status TEXT,
    error_type TEXT,
    first_token_ms REAL,
    queue_ms REAL,
    output_chars INTEGER,
    route TEXT
);
"""


class Database:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self.migrate()

    def connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.path, timeout=30, check_same_thread=False)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys=ON")
        con.execute("PRAGMA busy_timeout=30000")
        return con

    @contextmanager
    def tx(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            con = self.connect()
            try:
                con.execute("BEGIN")
                yield con
                con.commit()
            except Exception:
                con.rollback()
                raise
            finally:
                con.close()

    def migrate(self) -> None:
        with self._lock:
            con = self.connect()
            try:
                con.executescript(SCHEMA)
                # Migraciones aditivas seguras para instalaciones V8.x existentes.
                cols = {row[1] for row in con.execute("PRAGMA table_info(query_metrics)").fetchall()}
                for name, ddl in (
                    ("first_token_ms", "ALTER TABLE query_metrics ADD COLUMN first_token_ms REAL"),
                    ("queue_ms", "ALTER TABLE query_metrics ADD COLUMN queue_ms REAL"),
                    ("output_chars", "ALTER TABLE query_metrics ADD COLUMN output_chars INTEGER"),
                    ("route", "ALTER TABLE query_metrics ADD COLUMN route TEXT"),
                ):
                    if name not in cols:
                        con.execute(ddl)
                con.commit()
            finally:
                con.close()

    def execute(self, sql: str, params: Iterable[Any] = ()) -> None:
        with self.tx() as con:
            con.execute(sql, tuple(params))

    def query(self, sql: str, params: Iterable[Any] = ()) -> List[sqlite3.Row]:
        con = self.connect()
        try:
            return list(con.execute(sql, tuple(params)).fetchall())
        finally:
            con.close()

    def one(self, sql: str, params: Iterable[Any] = ()) -> Optional[sqlite3.Row]:
        rows = self.query(sql, params)
        return rows[0] if rows else None

    def audit(self, event_type: str, company_id: Optional[str], user_id: Optional[str], object_type: Optional[str] = None, object_id: Optional[str] = None, outcome: str = "ok", details: Optional[Dict[str, Any]] = None) -> None:
        safe = dict(details or {})
        for key in list(safe):
            if key.lower() in {"content", "prompt", "document_text", "secret", "token"}:
                safe[key] = "[REDACTED]"
        self.execute(
            "INSERT INTO audit_events(timestamp,company_id,user_id,event_type,object_type,object_id,outcome,details_json) VALUES(?,?,?,?,?,?,?,?)",
            (utcnow(), company_id, user_id, event_type, object_type, object_id, outcome, json.dumps(safe, ensure_ascii=False)),
        )
