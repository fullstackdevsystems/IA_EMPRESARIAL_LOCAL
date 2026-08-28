from __future__ import annotations

import json
import math
import sqlite3
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence

from .security import Principal


def cosine(a: Sequence[float], b: Sequence[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


class VectorStore(ABC):
    @abstractmethod
    def upsert(self, kind: str, vector_id: str, vector: Sequence[float], payload: Dict[str, Any]) -> None:
        raise NotImplementedError

    @abstractmethod
    def search(self, kind: str, query: Sequence[float], principal: Principal, limit: int = 8) -> List[Dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def delete(self, kind: str, vector_ids: Iterable[str]) -> None:
        raise NotImplementedError

    @abstractmethod
    def has(self, kind: str, vector_id: str) -> bool:
        raise NotImplementedError


class SQLiteVectorStore(VectorStore):
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(self.path)
        try:
            con.execute(
                "CREATE TABLE IF NOT EXISTS vectors("
                "kind TEXT NOT NULL, vector_id TEXT NOT NULL, company_id TEXT NOT NULL, "
                "user_id TEXT, scope TEXT NOT NULL DEFAULT 'company', vector_json TEXT NOT NULL, "
                "payload_json TEXT NOT NULL, PRIMARY KEY(kind,vector_id))"
            )
            con.execute("CREATE INDEX IF NOT EXISTS idx_vectors_scope ON vectors(kind,company_id,user_id,scope)")
            con.commit()
        finally:
            con.close()

    def upsert(self, kind, vector_id, vector, payload):
        con = sqlite3.connect(self.path)
        try:
            con.execute(
                "INSERT OR REPLACE INTO vectors(kind,vector_id,company_id,user_id,scope,vector_json,payload_json) VALUES(?,?,?,?,?,?,?)",
                (
                    kind,
                    vector_id,
                    str(payload.get("company_id", "")),
                    payload.get("user_id"),
                    str(payload.get("scope", "company")),
                    json.dumps(list(map(float, vector))),
                    json.dumps(payload, ensure_ascii=False),
                ),
            )
            con.commit()
        finally:
            con.close()

    def has(self, kind, vector_id):
        con = sqlite3.connect(self.path)
        try:
            return con.execute("SELECT 1 FROM vectors WHERE kind=? AND vector_id=?", (kind, vector_id)).fetchone() is not None
        finally:
            con.close()

    def search(self, kind, query, principal, limit=8):
        con = sqlite3.connect(self.path)
        con.row_factory = sqlite3.Row
        try:
            rows = con.execute(
                "SELECT vector_id,vector_json,payload_json FROM vectors "
                "WHERE kind=? AND company_id=? AND (scope='company' OR user_id=?)",
                (kind, principal.company_id, principal.user_id),
            ).fetchall()
        finally:
            con.close()
        scored = []
        for row in rows:
            scored.append(
                {
                    "vector_id": row["vector_id"],
                    "score": cosine(query, json.loads(row["vector_json"])),
                    "payload": json.loads(row["payload_json"]),
                }
            )
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:limit]

    def delete(self, kind, vector_ids):
        ids = list(dict.fromkeys(vector_ids))
        if not ids:
            return
        con = sqlite3.connect(self.path)
        try:
            con.executemany("DELETE FROM vectors WHERE kind=? AND vector_id=?", [(kind, x) for x in ids])
            con.commit()
        finally:
            con.close()


class QdrantVectorStore(VectorStore):
    """Embedded Qdrant when qdrant-client is installed.

    Security is enforced twice: company filter in Qdrant and post-filter in Python.
    """

    def __init__(self, path: str | Path):
        try:
            from qdrant_client import QdrantClient
            from qdrant_client.models import Distance, PointStruct, VectorParams
        except Exception as exc:
            raise RuntimeError("qdrant-client no esta instalado") from exc
        self._Distance = Distance
        self._PointStruct = PointStruct
        self._VectorParams = VectorParams
        self.client = QdrantClient(path=str(Path(path)))

    def _collection(self, kind: str) -> str:
        return "ia_empresarial_" + "".join(c if c.isalnum() else "_" for c in kind)[:40]

    def _ensure(self, kind: str, dimension: int) -> str:
        name = self._collection(kind)
        try:
            exists = self.client.collection_exists(name)
        except Exception:
            exists = any(c.name == name for c in self.client.get_collections().collections)
        if not exists:
            self.client.create_collection(
                name,
                vectors_config=self._VectorParams(size=int(dimension), distance=self._Distance.COSINE),
            )
        return name

    def upsert(self, kind, vector_id, vector, payload):
        name = self._ensure(kind, len(vector))
        self.client.upsert(
            name,
            points=[self._PointStruct(id=vector_id, vector=list(map(float, vector)), payload=payload)],
            wait=True,
        )

    def has(self, kind, vector_id):
        try:
            return bool(self.client.retrieve(self._collection(kind), ids=[vector_id], with_vectors=False))
        except Exception:
            return False

    def search(self, kind, query, principal, limit=8):
        try:
            from qdrant_client.models import FieldCondition, Filter, MatchValue

            name = self._collection(kind)
            qfilter = Filter(must=[FieldCondition(key="company_id", match=MatchValue(value=principal.company_id))])
            try:
                points = self.client.query_points(
                    name,
                    query=list(map(float, query)),
                    query_filter=qfilter,
                    limit=max(limit * 5, 20),
                    with_payload=True,
                ).points
            except Exception:
                points = self.client.search(
                    name,
                    query_vector=list(map(float, query)),
                    query_filter=qfilter,
                    limit=max(limit * 5, 20),
                    with_payload=True,
                )
            out = []
            for point in points:
                payload = dict(point.payload or {})
                if payload.get("scope", "company") != "company" and payload.get("user_id") != principal.user_id:
                    continue
                out.append({"vector_id": str(point.id), "score": float(point.score), "payload": payload})
                if len(out) >= limit:
                    break
            return out
        except Exception:
            return []

    def delete(self, kind, vector_ids):
        ids = list(dict.fromkeys(vector_ids))
        if not ids:
            return
        try:
            from qdrant_client.models import PointIdsList

            self.client.delete(self._collection(kind), points_selector=PointIdsList(points=ids), wait=True)
        except Exception:
            pass


def build_vector_store(cfg: Dict[str, Any]) -> VectorStore:
    if str(cfg.get("backend", "qdrant")).lower() == "qdrant":
        try:
            return QdrantVectorStore(cfg["qdrant_path"])
        except Exception:
            if not cfg.get("fallback_to_sqlite", True):
                raise
    return SQLiteVectorStore(cfg["sqlite_path"])
