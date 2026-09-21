from __future__ import annotations

import json
import math
import sqlite3
import uuid
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

        # Cierre explicito antes del desmontaje del interprete.
        import atexit
        atexit.register(self.close)

    def close(self) -> None:
        client = getattr(self, "client", None)
        if client is None:
            return
        try:
            client.close()
        except Exception:
            pass
        finally:
            self.client = None

    def _collection(self, kind: str) -> str:
        return "ia_empresarial_" + "".join(c if c.isalnum() else "_" for c in kind)[:40]

    @staticmethod
    def _migration_vector_values(value):
        """Normalize qdrant-client vector representations for upgrade checks."""
        if isinstance(value, dict):
            if len(value) != 1:
                raise ValueError("multi-vector migration is unsupported")
            value = next(iter(value.values()))
        return list(value)

    @classmethod
    def _migration_vectors_equal(cls, left, right) -> bool:
        a, b = cls._migration_vector_values(left), cls._migration_vector_values(right)
        return len(a) == len(b) and all(math.isclose(float(x), float(y), rel_tol=1e-6, abs_tol=1e-7) for x, y in zip(a, b))

    def _migration_canonical_vector(self, collection: str, value):
        """Apply the collection's documented dense-vector persistence semantics.

        Local Qdrant can expose a legacy cosine point in its pre-normalized
        form after reopen, while a new upsert is normalized.  Migration uses
        the collection configuration, not an embedding provider, to copy the
        canonical dense representation that Qdrant writes for COSINE.
        """
        params = self.client.get_collection(collection).config.params.vectors
        if isinstance(params, dict) or getattr(params, "multivector_config", None) is not None:
            raise ValueError("named or multi-vector migration is unsupported")
        vector = self._migration_vector_values(value)
        if len(vector) != int(params.size):
            raise ValueError("qdrant vector dimension mismatch")
        if str(params.distance).lower().endswith("cosine"):
            magnitude = math.sqrt(sum(float(item) * float(item) for item in vector))
            if magnitude == 0.0:
                raise ValueError("zero cosine vector migration is unsupported")
            return [float(item) / magnitude for item in vector]
        return vector

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
            qfilter = Filter(
                must=[
                    FieldCondition(
                        key="company_id",
                        match=MatchValue(value=principal.company_id),
                    )
                ],
                should=[
                    FieldCondition(
                        key="scope",
                        match=MatchValue(value="company"),
                    ),
                    FieldCondition(
                        key="user_id",
                        match=MatchValue(value=principal.user_id),
                    ),
                ],
            )
            try:
                points = self.client.query_points(
                    name,
                    query=list(map(float, query)),
                    query_filter=qfilter,
                    limit=limit,
                    with_payload=True,
                ).points
            except Exception:
                points = self.client.search(
                    name,
                    query_vector=list(map(float, query)),
                    query_filter=qfilter,
                    limit=limit,
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

    def _plan_scope_clone(self, source_company: str, source_user: str, target_company: str, target_user: str, vector_id_map=None, document_id_map=None, dataset_id_map=None):
        """Internal upgrade-only point copier; never deletes source points."""
        try:
            from qdrant_client.models import FieldCondition, Filter, MatchValue
            out = []
            for collection in self.client.get_collections().collections:
                name = collection.name
                offset = None
                while True:
                    points, offset = self.client.scroll(name, scroll_filter=Filter(must=[FieldCondition(key="company_id", match=MatchValue(value=source_company))]), limit=256, offset=offset, with_payload=True, with_vectors=True)
                    for point in points:
                        payload = dict(point.payload or {})
                        if payload.get("user_id") != source_user:
                            continue
                        vector_id_map = vector_id_map or {}
                        document_id_map = document_id_map or {}
                        dataset_id_map = dataset_id_map or {}
                        target_id = vector_id_map.get(str(point.id), str(uuid.uuid5(uuid.NAMESPACE_URL, f"legacy-qdrant|{name}|{point.id}|{target_company}|{target_user}")))
                        target_payload = {**payload, "company_id": target_company, "user_id": target_user}
                        if target_payload.get("document_id") in document_id_map:
                            target_payload["document_id"] = document_id_map[target_payload["document_id"]]
                        if target_payload.get("dataset_id") in dataset_id_map:
                            target_payload["dataset_id"] = dataset_id_map[target_payload["dataset_id"]]
                        existing = self.client.retrieve(name, ids=[target_id], with_payload=True, with_vectors=True)
                        # Scroll may return the pre-normalized input for cosine
                        # collections; retrieve is the canonical persisted value.
                        source_read = self.client.retrieve(name, ids=[str(point.id)], with_payload=False, with_vectors=True)
                        if len(source_read) != 1:
                            raise ValueError("qdrant source point unavailable")
                        vector = self._migration_canonical_vector(name, source_read[0].vector)
                        if existing:
                            candidate = existing[0]
                            if dict(candidate.payload or {}) != target_payload or not self._migration_vectors_equal(candidate.vector, vector):
                                raise ValueError("qdrant target conflict")
                            create = False
                        else:
                            create = True
                        out.append({"collection": name, "source_id": str(point.id), "target_id": target_id, "vector": vector, "payload": target_payload, "create": create})
                    if offset is None:
                        break
            return out
        except Exception:
            raise

    def _apply_scope_clone(self, points):
        """Internal upgrade-only apply; source points remain untouched."""
        for item in points:
            if item["create"]:
                self.client.upsert(item["collection"], points=[self._PointStruct(id=item["target_id"], vector=item["vector"], payload=item["payload"])], wait=True)
                read = self.client.retrieve(item["collection"], ids=[item["target_id"]], with_payload=True, with_vectors=True)
                if len(read) != 1:
                    raise RuntimeError("qdrant migration verification missing point")
                if dict(read[0].payload or {}) != item["payload"]:
                    raise RuntimeError("qdrant migration verification payload mismatch")
                actual = self._migration_canonical_vector(item["collection"], read[0].vector)
                if not self._migration_vectors_equal(actual, item["vector"]):
                    expected = self._migration_vector_values(item["vector"])
                    delta = max((abs(float(a) - float(b)) for a, b in zip(actual, expected)), default=float("inf"))
                    raise RuntimeError(f"qdrant migration verification vector mismatch dimensions={len(actual)}/{len(expected)} max_delta={delta:.8g}")


def build_vector_store(cfg: Dict[str, Any]) -> VectorStore:
    if str(cfg.get("backend", "qdrant")).lower() == "qdrant":
        try:
            return QdrantVectorStore(cfg["qdrant_path"])
        except Exception:
            if not cfg.get("fallback_to_sqlite", True):
                raise
    return SQLiteVectorStore(cfg["sqlite_path"])
