"""Explicit, fail-closed legacy scope migration for commercial upgrades.

This is deliberately not imported by runtime request paths.  It requires both
source and target scopes and is intended for a controlled upgrade operation.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
import uuid
from datetime import datetime, timezone
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from enterprise_ai.database import Database
from enterprise_deliverable_registry import GovernedDeliverableRegistry, normalize_deliverable_scope
from enterprise_identity import EnterpriseIdentityStore, IdentityError
from enterprise_knowledge_store import EnterpriseKnowledgeStore
from enterprise_sql_gateway import EnterpriseSqlConnectionStore
from enterprise_tenant_registry import EnterpriseTenantRegistry, TenantRegistryError
from enterprise_source_registry import _prepare_scope_clone, _write_migrated_registry as _write_source_registry
from enterprise_query_registry import _prepare_source_clones, _write_migrated_registry as _write_query_registry
from enterprise_ai.vector_store import QdrantVectorStore


class LegacyScopeMigrationError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _canonical(value: Dict[str, Any]) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _digest(value: Dict[str, Any], field: str) -> Dict[str, Any]:
    candidate = dict(value)
    candidate.pop(field, None)
    candidate[field] = hashlib.sha256(_canonical(candidate)).hexdigest()
    return candidate


def _safe_report(value: Any) -> Any:
    """Return an allowlisted, structural-only migration evidence value."""
    if not isinstance(value, dict):
        return {"status": "UNAVAILABLE"}
    allowed = {"status", "mutated", "found", "migrated", "skipped", "enterprise_ai_rows", "vector_rows", "qdrant_points", "documents", "datasets", "source_registry_records"}
    result: Dict[str, Any] = {}
    for key in allowed:
        item = value.get(key)
        if isinstance(item, (str, int, float, bool)) or item is None:
            result[key] = item
        elif isinstance(item, dict):
            result[key] = {str(k): int(v) if isinstance(v, bool) else v for k, v in item.items() if isinstance(v, (str, int, float, bool)) or v is None}
    return result


@dataclass(frozen=True)
class MigrationScopes:
    source: Dict[str, Any]
    target: Dict[str, Any]


class LegacyScopeMigrator:
    """Coordinates canonical stores; source records are never deleted."""

    def __init__(self, runtime_root: Path, *, fail_after_step: str | None = None):
        self.runtime_root = Path(runtime_root).resolve()
        self.reports = self.runtime_root / "workspace" / "Reportes"
        self.tenants = EnterpriseTenantRegistry(self.reports / ".tenants")
        self.identity = EnterpriseIdentityStore(self.reports / ".identity", self.tenants)
        self.fail_after_step = fail_after_step

    def _scopes(self, source_scope: Dict[str, Any], target_scope: Dict[str, Any]) -> MigrationScopes:
        source = normalize_deliverable_scope(source_scope)
        requested = normalize_deliverable_scope(target_scope)
        try:
            tenant = self.tenants.assert_active(requested["company_id"])
            user = self.identity.get(requested["user_id"])
        except (TenantRegistryError, IdentityError) as exc:
            raise LegacyScopeMigrationError("MIGRATION_TARGET_IDENTITY_INVALID", "Tenant o usuario destino no es válido") from exc
        if user.get("status") != "ACTIVE" or user.get("tenant_id") != tenant["tenant_id"]:
            raise LegacyScopeMigrationError("MIGRATION_TARGET_IDENTITY_INVALID", "Usuario destino fuera de tenant activo")
        target = {**requested, "company_id": tenant["tenant_id"]}
        if source == target:
            raise LegacyScopeMigrationError("MIGRATION_SCOPE_UNCHANGED", "Source y target deben ser scopes distintos")
        return MigrationScopes(source=source, target=target)

    def _stores(self):
        # Source readers intentionally do not attach the target tenant registry:
        # a legacy tenant may not exist in the new registry.  Target writers do.
        return (
            GovernedDeliverableRegistry(self.reports, tenant_registry=None),
            GovernedDeliverableRegistry(self.reports, tenant_registry=self.tenants),
            EnterpriseKnowledgeStore(self.reports / ".knowledge", tenant_registry=None),
            EnterpriseKnowledgeStore(self.reports / ".knowledge", tenant_registry=self.tenants),
            EnterpriseSqlConnectionStore(self.reports / ".sql_connections", None),
            EnterpriseSqlConnectionStore(self.reports / ".sql_connections", self.tenants),
        )

    def _candidate(self, kind: str, record: Dict[str, Any], target: Dict[str, Any]) -> Dict[str, Any]:
        field = "record_fingerprint_sha256" if kind == "deliverables" else "fingerprint_sha256"
        return _digest({**record, "scope": target}, field)

    def _target_conflict(self, getter, candidate: Dict[str, Any], target: Dict[str, Any], identifier: str) -> bool:
        try:
            existing = getter(target, identifier)
        except Exception as exc:
            if getattr(exc, "code", "") in {"RUN_NOT_FOUND", "KNOWLEDGE_NOT_FOUND", "SQL_CONNECTION_NOT_FOUND"}:
                return False
            raise
        return existing != candidate

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()

    def _safe_knowledge_path(self, value: str, company_id: str) -> Path:
        root = (self.runtime_root / "workspace" / "Conocimiento").resolve()
        company_root = (root / company_id).resolve()
        candidate = Path(value)
        if not candidate.is_absolute():
            raise LegacyScopeMigrationError("MIGRATION_PATH_INVALID", "Path legado no es absoluto gobernado")
        resolved = candidate.resolve(strict=True)
        try:
            resolved.relative_to(company_root)
        except ValueError as exc:
            raise LegacyScopeMigrationError("MIGRATION_PATH_INVALID", "Path legado fuera de Conocimiento gobernado") from exc
        if resolved.is_symlink() or not resolved.is_file():
            raise LegacyScopeMigrationError("MIGRATION_PATH_INVALID", "Path legado no es un archivo regular")
        return resolved

    @staticmethod
    def _target_id(kind: str, source_id: str, scopes: MigrationScopes) -> str:
        return str(uuid.uuid5(uuid.NAMESPACE_URL, f"legacy-scope-migration|{kind}|{source_id}|{scopes.source['company_id']}|{scopes.source['user_id']}|{scopes.target['company_id']}|{scopes.target['user_id']}"))

    def _path_store_plan(self, con: sqlite3.Connection, scopes: MigrationScopes) -> Dict[str, Any]:
        """Preflight document/dataset bytes and their relational metadata.

        This deliberately uses only the established SQLite schema and physical
        Conocimiento root.  It never accepts an arbitrary stored_path.
        """
        con.row_factory = sqlite3.Row
        tables = {row[0] for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not {"documents", "datasets"}.issubset(tables):
            return {"documents": [], "datasets": [], "path_map": {}, "vector_id_map": {}, "document_id_map": {}, "dataset_id_map": {}}
        documents: List[Dict[str, Any]] = []
        path_map: Dict[str, str] = {}
        vector_id_map: Dict[str, str] = {}
        document_id_map: Dict[str, str] = {}
        for row in con.execute("SELECT * FROM documents WHERE company_id=? AND (user_id=? OR user_id IS NULL)", (scopes.source["company_id"], scopes.source["user_id"])).fetchall():
            source = dict(row)
            source_id = str(source["id"])
            target_id = self._target_id("document", source_id, scopes)
            existing_id = con.execute("SELECT * FROM documents WHERE id=?", (target_id,)).fetchone()
            owner = scopes.target["user_id"] if source["scope"] == "user" else None
            existing_name = con.execute("SELECT id FROM documents WHERE company_id=? AND scope=? AND user_id IS ? AND name=?", (scopes.target["company_id"], source["scope"], owner, source["name"])).fetchone()
            if existing_name and str(existing_name["id"]) != target_id:
                raise LegacyScopeMigrationError("MIGRATION_DOCUMENT_CONFLICT", "Conflicto de nombre de documento destino")
            versions = [dict(item) for item in con.execute("SELECT * FROM document_versions WHERE document_id=? ORDER BY version", (source_id,)).fetchall()]
            chunks = [dict(item) for item in con.execute("SELECT * FROM document_chunks WHERE document_id=? ORDER BY version,ordinal,id", (source_id,)).fetchall()]
            if not versions:
                raise LegacyScopeMigrationError("MIGRATION_DOCUMENT_INTEGRITY_INVALID", "Documento sin versiones")
            source_root = (self.runtime_root / "workspace" / "Conocimiento" / scopes.source["company_id"] / source_id).resolve()
            files: List[Dict[str, str]] = []
            for version in versions:
                physical = self._safe_knowledge_path(str(version["stored_path"]), scopes.source["company_id"])
                try:
                    relative = physical.relative_to(source_root)
                except ValueError as exc:
                    raise LegacyScopeMigrationError("MIGRATION_DOCUMENT_PATH_INVALID", "Versión fuera del directorio del documento") from exc
                actual = self._sha256(physical)
                if actual != str(version["file_hash"]):
                    raise LegacyScopeMigrationError("MIGRATION_DOCUMENT_HASH_INVALID", "Hash de versión inválido")
                target_path = (self.runtime_root / "workspace" / "Conocimiento" / scopes.target["company_id"] / target_id / relative).resolve()
                if target_path.exists() and (not target_path.is_file() or self._sha256(target_path) != actual):
                    raise LegacyScopeMigrationError("MIGRATION_DOCUMENT_PATH_CONFLICT", "Conflicto físico de documento destino")
                files.append({"source": str(physical), "target": str(target_path), "sha256": actual})
                path_map[str(physical)] = str(target_path)
            current_source = self._safe_knowledge_path(str(source["stored_path"]), scopes.source["company_id"])
            if self._sha256(current_source) != str(source["current_hash"]):
                raise LegacyScopeMigrationError("MIGRATION_DOCUMENT_HASH_INVALID", "Hash actual de documento inválido")
            if str(current_source) not in path_map:
                raise LegacyScopeMigrationError("MIGRATION_DOCUMENT_INTEGRITY_INVALID", "Documento actual no está en versiones")
            target_versions = []
            for version in versions:
                target_versions.append({**version, "id": self._target_id("document-version", str(version["id"]), scopes), "document_id": target_id, "stored_path": path_map[str(self._safe_knowledge_path(str(version["stored_path"]), scopes.source["company_id"]))]})
            target_chunks = []
            for chunk in chunks:
                vector_id = str(chunk["vector_id"])
                target_vector = vector_id_map.setdefault(vector_id, self._target_id("document-vector", vector_id, scopes))
                target_chunks.append({**chunk, "id": self._target_id("document-chunk", str(chunk["id"]), scopes), "document_id": target_id, "vector_id": target_vector})
            target = {**source, "id": target_id, "company_id": scopes.target["company_id"], "user_id": owner, "stored_path": path_map[str(current_source)]}
            if existing_id and dict(existing_id) != target:
                raise LegacyScopeMigrationError("MIGRATION_DOCUMENT_CONFLICT", "Conflicto de ID de documento destino")
            documents.append({"source": source, "target": target, "versions": target_versions, "chunks": target_chunks, "files": files, "create": existing_id is None})
            document_id_map[source_id] = target_id
        datasets: List[Dict[str, Any]] = []
        dataset_id_map: Dict[str, str] = {}
        for row in con.execute("SELECT * FROM datasets WHERE company_id=? AND (user_id=? OR user_id IS NULL)", (scopes.source["company_id"], scopes.source["user_id"])).fetchall():
            source = dict(row); source_id = str(source["id"]); target_id = self._target_id("dataset", source_id, scopes)
            physical = self._safe_knowledge_path(str(source["path"]), scopes.source["company_id"])
            if source.get("file_hash") and self._sha256(physical) != str(source["file_hash"]):
                raise LegacyScopeMigrationError("MIGRATION_DATASET_HASH_INVALID", "Hash de dataset inválido")
            owner = scopes.target["user_id"] if source["scope"] == "user" else None
            target_path = Path(path_map.get(str(physical), str((self.runtime_root / "workspace" / "Conocimiento" / scopes.target["company_id"] / "datasets" / target_id / physical.name).resolve())))
            if target_path.exists() and (not target_path.is_file() or self._sha256(target_path) != self._sha256(physical)):
                raise LegacyScopeMigrationError("MIGRATION_DATASET_PATH_CONFLICT", "Conflicto físico de dataset destino")
            existing = con.execute("SELECT * FROM datasets WHERE id=?", (target_id,)).fetchone()
            target = {**source, "id": target_id, "company_id": scopes.target["company_id"], "user_id": owner, "path": str(target_path)}
            if existing and dict(existing) != target:
                raise LegacyScopeMigrationError("MIGRATION_DATASET_CONFLICT", "Conflicto de ID de dataset destino")
            datasets.append({"source": source, "target": target, "file": {"source": str(physical), "target": str(target_path), "sha256": self._sha256(physical)}, "create": existing is None})
            dataset_id_map[source_id] = target_id
        return {"documents": documents, "datasets": datasets, "path_map": path_map, "vector_id_map": vector_id_map, "document_id_map": document_id_map, "dataset_id_map": dataset_id_map}

    def _sqlite_plan(self, scopes: MigrationScopes) -> Dict[str, Any]:
        path = self.runtime_root / "data" / "enterprise" / "enterprise_ai.sqlite3"
        if not path.exists():
            return {"path": path, "tables": [], "rows": 0, "path_stores": {"documents": [], "datasets": [], "vector_id_map": {}, "document_id_map": {}, "dataset_id_map": {}}}
        # Do not instantiate Database here: its constructor may apply additive
        # schema migrations.  Planning/dry-run must be byte-for-byte read-only.
        con = sqlite3.connect(path)
        try:
            tables = [row[0] for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'") if str(row[0]).replace("_", "").isalnum()]
            plan = []
            for table in tables:
                columns = {row[1] for row in con.execute(f'PRAGMA table_info("{table}")')}
                if "company_id" not in columns:
                    continue
                if table in {"documents", "datasets", "document_versions", "document_chunks"}:
                    continue
                where = 'company_id=?'
                params: List[Any] = [scopes.source["company_id"]]
                if "user_id" in columns:
                    where += ' AND user_id=?'; params.append(scopes.source["user_id"])
                count = con.execute(f'SELECT COUNT(*) FROM "{table}" WHERE {where}', tuple(params)).fetchone()[0]
                if count:
                    if table != "memories" or "id" not in columns:
                        raise LegacyScopeMigrationError("MIGRATION_ENTERPRISE_AI_UNSUPPORTED", "Tabla Enterprise AI no soporta clonación gobernada")
                    con.row_factory = sqlite3.Row
                    rows = [dict(row) for row in con.execute(f'SELECT * FROM "{table}" WHERE {where}', tuple(params)).fetchall()]
                    copies = []
                    for row in rows:
                        candidate = {**row, "id": self._target_id("memory", str(row["id"]), scopes), "company_id": scopes.target["company_id"], "user_id": scopes.target["user_id"]}
                        existing = con.execute(f'SELECT * FROM "{table}" WHERE id=?', (candidate["id"],)).fetchone()
                        if existing and dict(existing) != candidate:
                            raise LegacyScopeMigrationError("MIGRATION_ENTERPRISE_AI_CONFLICT", "Conflicto de memoria destino")
                        copies.append(candidate)
                    plan.append({"table": table, "columns": sorted(columns), "count": int(count), "records": copies})
            path_stores = self._path_store_plan(con, scopes)
        finally:
            con.close()
        return {"path": path, "tables": plan, "rows": sum(item["count"] for item in plan), "path_stores": path_stores}

    def _sqlite_preflight(self, plan: Dict[str, Any], scopes: MigrationScopes) -> None:
        if not plan["tables"]:
            return
        con = sqlite3.connect(plan["path"])
        try:
            con.execute("BEGIN")
            self._sqlite_apply(con, plan["tables"], scopes)
            con.rollback()
        except sqlite3.Error as exc:
            con.rollback()
            raise LegacyScopeMigrationError("MIGRATION_ENTERPRISE_AI_CONFLICT", "Conflicto de datos Enterprise AI en destino") from exc
        finally:
            con.close()

    def _vector_plan(self, scopes: MigrationScopes, vector_id_map: Dict[str, str] | None = None, document_id_map: Dict[str, str] | None = None, dataset_id_map: Dict[str, str] | None = None) -> Dict[str, Any]:
        qdrant = self.runtime_root / "data" / "enterprise" / "qdrant"
        qdrant_points = []
        if qdrant.exists() and any(path.is_file() for path in qdrant.rglob("*")):
            qdrant_store = None
            try:
                qdrant_store = QdrantVectorStore(qdrant)
                qdrant_points = qdrant_store._plan_scope_clone(scopes.source["company_id"], scopes.source["user_id"], scopes.target["company_id"], scopes.target["user_id"], vector_id_map or {}, document_id_map or {}, dataset_id_map or {})
            except Exception as exc:
                raise LegacyScopeMigrationError("MIGRATION_QDRANT_CONFLICT", "No se pudo preflight Qdrant") from exc
            finally:
                if qdrant_store is not None:
                    qdrant_store.close()
        path = self.runtime_root / "data" / "enterprise" / "vectors.sqlite3"
        if not path.exists():
            return {"path": path, "rows": [], "qdrant_path": qdrant, "qdrant_points": qdrant_points}
        con = sqlite3.connect(path)
        try:
            exists = con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='vectors'").fetchone()
            if not exists:
                return {"path": path, "rows": [], "qdrant_path": qdrant, "qdrant_points": qdrant_points}
            rows = con.execute("SELECT kind,vector_id,vector_json,payload_json,scope FROM vectors WHERE company_id=? AND user_id=?", (scopes.source["company_id"], scopes.source["user_id"])).fetchall()
            prepared = []
            for kind, vector_id, vector_json, payload_json, vector_scope in rows:
                try: payload = json.loads(payload_json)
                except Exception as exc: raise LegacyScopeMigrationError("MIGRATION_VECTOR_INTEGRITY_INVALID", "Payload vectorial ilegible") from exc
                if not isinstance(payload, dict) or payload.get("company_id") != scopes.source["company_id"] or payload.get("user_id") != scopes.source["user_id"]:
                    raise LegacyScopeMigrationError("MIGRATION_VECTOR_INTEGRITY_INVALID", "Payload vectorial fuera de scope")
                payload.update({"company_id": scopes.target["company_id"], "user_id": scopes.target["user_id"]})
                if document_id_map and payload.get("document_id") in document_id_map:
                    payload["document_id"] = document_id_map[payload["document_id"]]
                if dataset_id_map and payload.get("dataset_id") in dataset_id_map:
                    payload["dataset_id"] = dataset_id_map[payload["dataset_id"]]
                target_id = (vector_id_map or {}).get(str(vector_id), str(uuid.uuid5(uuid.NAMESPACE_URL, f"legacy-vector|{kind}|{vector_id}|{scopes.target['company_id']}|{scopes.target['user_id']}")))
                target_payload = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                existing = con.execute("SELECT vector_json,payload_json,company_id,user_id,scope FROM vectors WHERE kind=? AND vector_id=?", (kind, target_id)).fetchone()
                if existing and tuple(existing) != (vector_json, target_payload, scopes.target["company_id"], scopes.target["user_id"], vector_scope):
                    raise LegacyScopeMigrationError("MIGRATION_VECTOR_CONFLICT", "Conflicto vectorial en destino")
                prepared.append((str(kind), target_id, vector_json, target_payload, vector_scope, not bool(existing)))
            return {"path": path, "rows": prepared, "qdrant_path": qdrant, "qdrant_points": qdrant_points}
        finally:
            con.close()

    @staticmethod
    def _vector_apply(plan: Dict[str, Any], scopes: MigrationScopes) -> None:
        if plan["rows"]:
            con = sqlite3.connect(plan["path"])
            try:
                con.execute("BEGIN")
                for kind, vector_id, vector_json, payload, vector_scope, create in plan["rows"]:
                    if create:
                        con.execute("INSERT INTO vectors(kind,vector_id,company_id,user_id,scope,vector_json,payload_json) VALUES(?,?,?,?,?,?,?)", (kind, vector_id, scopes.target["company_id"], scopes.target["user_id"], vector_scope, vector_json, payload))
                con.commit()
            except Exception:
                con.rollback(); raise
            finally:
                con.close()
        if plan.get("qdrant_points"):
            store = QdrantVectorStore(plan["qdrant_path"])
            try:
                store._apply_scope_clone(plan["qdrant_points"])
            finally:
                store.close()


    def _source_registry_plan(
        self,
        source_identity: Dict[str, Any] | None,
        target_identity: Dict[str, Any] | None,
        source_id_map: Dict[str, str] | None,
        query_id_map: Dict[str, str] | None,
    ) -> Dict[str, Any]:
        path = (
            self.runtime_root
            / "config"
            / "enterprise_sources.json"
        )
        query_path = (
            self.runtime_root
            / "config"
            / "enterprise_queries.json"
        )

        if not path.is_file():
            return {
                "sources": None,
                "queries": None,
                "source_count": 0,
            }

        try:
            source_payload = json.loads(
                path.read_text(
                    encoding="utf-8"
                )
            )
        except Exception as exc:
            raise LegacyScopeMigrationError(
                "MIGRATION_SOURCE_REGISTRY_INVALID",
                "Source registry ilegible",
            ) from exc

        if (
            source_identity is None
            or target_identity is None
        ):
            # Do not silently infer Source Registry's non-user scope from the
            # user-scoped legacy stores.
            if any(
                isinstance(item, dict)
                and item.get("scope")
                for item in source_payload.get(
                    "sources",
                    [],
                )
            ):
                raise LegacyScopeMigrationError(
                    "MIGRATION_SOURCE_MAPPING_REQUIRED",
                    "Source Registry requiere mapping explícito",
                )

            return {
                "sources": None,
                "queries": None,
                "source_count": 0,
            }

        try:
            source_candidate, mappings = (
                _prepare_scope_clone(
                    source_payload,
                    source_identity,
                    target_identity,
                    dict(
                        source_id_map
                        or {}
                    ),
                )
            )

            query_payload = (
                json.loads(
                    query_path.read_text(
                        encoding="utf-8"
                    )
                )
                if query_path.is_file()
                else None
            )

            query_candidate = (
                _prepare_source_clones(
                    query_payload,
                    mappings,
                    dict(
                        query_id_map
                        or {}
                    ),
                )
                if (
                    mappings
                    and query_payload is not None
                )
                else query_payload
            )

        except Exception as exc:
            raise LegacyScopeMigrationError(
                "MIGRATION_SOURCE_REGISTRY_CONFLICT",
                "Source Registry no puede migrarse de forma gobernada",
            ) from exc

        source_changed = (
            bool(mappings)
            and source_candidate
            != source_payload
        )

        query_changed = (
            bool(mappings)
            and query_payload is not None
            and query_candidate
            != query_payload
        )

        return {
            "sources":
                source_candidate
                if source_changed
                else None,

            "queries":
                query_candidate
                if query_changed
                else None,

            "source_count":
                len(mappings),

            "source_path":
                path,

            "query_path":
                query_path,
        }


    def _sqlite_apply(
        self,
        con: sqlite3.Connection,
        tables: Iterable[Dict[str, Any]],
        scopes: MigrationScopes,
    ) -> int:
        """Apply Enterprise AI rows and return the number actually mutated."""
        mutated = 0

        for item in tables:
            table = item["table"]

            if item.get("records") is not None:
                mutated += self._insert_rows(
                    con,
                    table,
                    item["records"],
                )
                continue

            columns = set(
                item["columns"]
            )

            sets = [
                'company_id=?'
            ]

            params: List[Any] = [
                scopes.target["company_id"]
            ]

            if "user_id" in columns:
                sets.append(
                    'user_id=?'
                )
                params.append(
                    scopes.target["user_id"]
                )

            where = 'company_id=?'

            params.append(
                scopes.source["company_id"]
            )

            if "user_id" in columns:
                where += ' AND user_id=?'
                params.append(
                    scopes.source["user_id"]
                )

            cursor = con.execute(
                f'UPDATE "{table}" '
                f'SET {", ".join(sets)} '
                f'WHERE {where}',
                tuple(params),
            )

            if (
                cursor.rowcount is not None
                and cursor.rowcount > 0
            ):
                mutated += int(
                    cursor.rowcount
                )

        return mutated

    def _stage_path_stores(self, path_stores: Dict[str, Any], staging: Path) -> Dict[str, Path]:
        """Copy every governed physical input before any persistent write."""
        staged: Dict[str, Path] = {}
        items: List[Dict[str, str]] = []
        for document in path_stores["documents"]:
            items.extend(document["files"])
        items.extend(dataset["file"] for dataset in path_stores["datasets"])
        for item in items:
            target = item["target"]
            if target in staged:
                continue
            staged_path = staging / hashlib.sha256(target.encode("utf-8")).hexdigest()
            staged_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item["source"], staged_path)
            if self._sha256(staged_path) != item["sha256"]:
                raise LegacyScopeMigrationError("MIGRATION_STAGE_HASH_INVALID", "Hash de staging inválido")
            staged[target] = staged_path
        return staged


    def _materialize_staged(
        self,
        staged: Dict[str, Path],
        path_stores: Dict[str, Any],
    ) -> int:
        """Materialize staged customer bytes and report actual files created."""
        expected: Dict[str, str] = {}

        for document in path_stores["documents"]:
            expected.update(
                {
                    item["target"]: item["sha256"]
                    for item in document["files"]
                }
            )

        expected.update(
            {
                item["file"]["target"]:
                    item["file"]["sha256"]
                for item in path_stores["datasets"]
            }
        )

        created = 0

        for target_text, stage_path in staged.items():
            target = Path(target_text)
            target.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            if target.exists():
                if (
                    self._sha256(target)
                    != expected[target_text]
                ):
                    raise LegacyScopeMigrationError(
                        "MIGRATION_TARGET_PATH_CONFLICT",
                        "Path destino no es idempotente",
                    )
                continue

            shutil.copy2(
                stage_path,
                target,
            )

            if (
                self._sha256(target)
                != expected[target_text]
            ):
                raise LegacyScopeMigrationError(
                    "MIGRATION_TARGET_HASH_INVALID",
                    "Hash de bytes destino inválido",
                )

            created += 1

        return created

    @staticmethod
    def _insert_rows(con: sqlite3.Connection, table: str, rows: Iterable[Dict[str, Any]]) -> int:
        inserted = 0
        for row in rows:
            existing = con.execute(f'SELECT 1 FROM "{table}" WHERE id=?', (row["id"],)).fetchone()
            if existing:
                continue
            columns = list(row)
            con.execute(f'INSERT INTO "{table}" ({",".join(columns)}) VALUES ({",".join("?" for _ in columns)})', tuple(row[column] for column in columns))
            inserted += 1
        return inserted


    def _path_store_apply(
        self,
        con: sqlite3.Connection,
        path_stores: Dict[str, Any],
    ) -> Tuple[int, int, int]:
        """Apply path-store metadata and return actual inserted-row counts."""
        documents = 0
        datasets = 0
        total_rows = 0

        for item in path_stores["documents"]:
            inserted = self._insert_rows(
                con,
                "documents",
                [item["target"]],
            )

            documents += inserted
            total_rows += inserted

            total_rows += self._insert_rows(
                con,
                "document_versions",
                item["versions"],
            )

            total_rows += self._insert_rows(
                con,
                "document_chunks",
                item["chunks"],
            )

        for item in path_stores["datasets"]:
            inserted = self._insert_rows(
                con,
                "datasets",
                [item["target"]],
            )

            datasets += inserted
            total_rows += inserted

        return (
            documents,
            datasets,
            total_rows,
        )

    def _verify_path_stores(self, path_stores: Dict[str, Any]) -> None:
        path = self.runtime_root / "data" / "enterprise" / "enterprise_ai.sqlite3"
        if not path.exists():
            return
        con = sqlite3.connect(path)
        con.row_factory = sqlite3.Row
        try:
            for item in path_stores["documents"]:
                if dict(con.execute("SELECT * FROM documents WHERE id=?", (item["target"]["id"],)).fetchone() or {}) != item["target"]:
                    raise LegacyScopeMigrationError("MIGRATION_TARGET_VERIFY_FAILED", "Documento destino ilegible")
                if len(con.execute("SELECT id FROM document_versions WHERE document_id=?", (item["target"]["id"],)).fetchall()) != len(item["versions"]):
                    raise LegacyScopeMigrationError("MIGRATION_TARGET_VERIFY_FAILED", "Versiones destino incompletas")
                if len(con.execute("SELECT id FROM document_chunks WHERE document_id=?", (item["target"]["id"],)).fetchall()) != len(item["chunks"]):
                    raise LegacyScopeMigrationError("MIGRATION_TARGET_VERIFY_FAILED", "Chunks destino incompletos")
                for file in item["files"]:
                    if self._sha256(Path(file["target"])) != file["sha256"]:
                        raise LegacyScopeMigrationError("MIGRATION_TARGET_VERIFY_FAILED", "Bytes de documento destino inválidos")
            for item in path_stores["datasets"]:
                if dict(con.execute("SELECT * FROM datasets WHERE id=?", (item["target"]["id"],)).fetchone() or {}) != item["target"] or self._sha256(Path(item["file"]["target"])) != item["file"]["sha256"]:
                    raise LegacyScopeMigrationError("MIGRATION_TARGET_VERIFY_FAILED", "Dataset destino ilegible")
        finally:
            con.close()

    def _snapshot(self) -> Tuple[Path, List[Tuple[Path, Path | None]]]:
        staging = Path(tempfile.mkdtemp(prefix="ia-legacy-scope-migration-"))
        targets = [self.reports / ".registry", self.reports / ".knowledge", self.reports / ".sql_connections", self.reports / ".migration_audit", self.runtime_root / "workspace" / "Conocimiento", self.runtime_root / "data" / "enterprise" / "enterprise_ai.sqlite3", self.runtime_root / "data" / "enterprise" / "vectors.sqlite3", self.runtime_root / "data" / "enterprise" / "qdrant", self.runtime_root / "config" / "enterprise_sources.json", self.runtime_root / "config" / "enterprise_queries.json"]
        entries = []
        for index, target in enumerate(targets):
            backup = staging / str(index)
            if target.exists():
                if target.is_dir(): shutil.copytree(target, backup)
                else: backup.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(target, backup)
                entries.append((target, backup))
            else:
                entries.append((target, None))
        return staging, entries

    @staticmethod
    def _restore_snapshot(entries: Iterable[Tuple[Path, Path | None]]) -> None:
        for target, backup in entries:
            if target.exists():
                if target.is_dir(): shutil.rmtree(target)
                else: target.unlink()
            if backup is not None:
                if backup.is_dir(): shutil.copytree(backup, target)
                else: target.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(backup, target)

    def _write_evidence(self, report: Dict[str, Any]) -> str:
        """Persist only sanitized structural migration evidence after success."""
        directory = self.reports / ".migration_audit"
        directory.mkdir(parents=True, exist_ok=True)
        payload = _safe_report({**report, "recorded_at": datetime.now(timezone.utc).isoformat()})
        payload["evidence_fingerprint_sha256"] = hashlib.sha256(_canonical(payload)).hexdigest()
        target = directory / f"legacy-scope-{uuid.uuid4().hex}.json"
        temporary = target.with_suffix(".tmp")
        temporary.write_bytes(_canonical(payload))
        os.replace(temporary, target)
        return target.name

    def plan(self, *, source_scope: Dict[str, Any], target_scope: Dict[str, Any], source_registry_source_scope: Dict[str, Any] | None = None, source_registry_target_scope: Dict[str, Any] | None = None, source_id_map: Dict[str, str] | None = None, query_id_map: Dict[str, str] | None = None) -> Dict[str, Any]:
        scopes = self._scopes(source_scope, target_scope)
        source_deliverables, target_deliverables, source_knowledge, target_knowledge, source_sql, target_sql = self._stores()
        records = {
            "deliverables": source_deliverables.list(scopes.source, limit=500),
            "knowledge": source_knowledge.list(scopes.source, include_inactive=True),
            "sql_profiles": source_sql.list(scopes.source),
        }
        actions: Dict[str, List[Dict[str, Any]]] = {key: [] for key in records}
        target_getters = {"deliverables": target_deliverables.get, "knowledge": target_knowledge.get, "sql_profiles": target_sql.get}
        id_keys = {"deliverables": "run_id", "knowledge": "knowledge_id", "sql_profiles": "connection_id"}
        for kind, items in records.items():
            for record in items:
                identifier = str(record[id_keys[kind]])
                candidate = self._candidate("deliverables" if kind == "deliverables" else kind, record, scopes.target)
                conflict = self._target_conflict(target_getters[kind], candidate, scopes.target, identifier)
                actions[kind].append({"id": identifier, "state": "CONFLICT" if conflict else "MIGRATE", "candidate": candidate})
        if any(action["state"] == "CONFLICT" for values in actions.values() for action in values):
            raise LegacyScopeMigrationError("MIGRATION_TARGET_CONFLICT", "Existen conflictos en el scope destino")
        source_registry = self._source_registry_plan(source_registry_source_scope, source_registry_target_scope, source_id_map, query_id_map)
        sqlite = self._sqlite_plan(scopes); self._sqlite_preflight(sqlite, scopes)
        paths = sqlite.get("path_stores", {})
        vectors = self._vector_plan(scopes, paths.get("vector_id_map"), paths.get("document_id_map"), paths.get("dataset_id_map"))
        return _safe_report({"status": "PLANNED", "found": {key: len(value) for key, value in records.items()}, "enterprise_ai_rows": sqlite["rows"], "documents": len(paths.get("documents", [])), "datasets": len(paths.get("datasets", [])), "vector_rows": len(vectors["rows"]), "qdrant_points": len(vectors.get("qdrant_points") or []), "source_registry_records": source_registry["source_count"]}), (scopes, records, sqlite, vectors, source_registry)


    def migrate(
        self,
        *,
        source_scope: Dict[str, Any],
        target_scope: Dict[str, Any],
        dry_run: bool = True,
        source_registry_source_scope: Dict[str, Any] | None = None,
        source_registry_target_scope: Dict[str, Any] | None = None,
        source_id_map: Dict[str, str] | None = None,
        query_id_map: Dict[str, str] | None = None,
    ) -> Dict[str, Any]:
        report, internal = self.plan(
            source_scope=source_scope,
            target_scope=target_scope,
            source_registry_source_scope=source_registry_source_scope,
            source_registry_target_scope=source_registry_target_scope,
            source_id_map=source_id_map,
            query_id_map=query_id_map,
        )

        if dry_run:
            return {
                **report,
                "status": "DRY_RUN",
                "mutated": False,
            }

        (
            scopes,
            records,
            sqlite_plan,
            vector_plan,
            source_registry,
        ) = internal

        snapshot, entries = self._snapshot()

        migrated = {
            "deliverables": 0,
            "knowledge": 0,
            "sql_profiles": 0,
            "enterprise_ai_rows": 0,
            "documents": 0,
            "datasets": 0,
            "vector_rows": 0,
            "qdrant_points": 0,
        }

        path_files_created = 0
        path_rows_created = 0

        registry_sources_changed = (
            source_registry["sources"]
            is not None
        )

        registry_queries_changed = (
            source_registry["queries"]
            is not None
        )

        try:
            staged = self._stage_path_stores(
                sqlite_plan.get(
                    "path_stores",
                    {},
                ),
                snapshot / "physical-stage",
            )

            (
                _,
                target_deliverables,
                _,
                target_knowledge,
                _,
                target_sql,
            ) = self._stores()

            for record in records["deliverables"]:
                _, created = (
                    target_deliverables
                    ._import_migrated_record(
                        record,
                        scopes.target,
                    )
                )

                migrated["deliverables"] += int(
                    created
                )

            if self.fail_after_step == "deliverables":
                raise RuntimeError(
                    "induced migration failure"
                )

            for record in records["knowledge"]:
                _, created = (
                    target_knowledge
                    ._import_migrated_record(
                        record,
                        scopes.target,
                    )
                )

                migrated["knowledge"] += int(
                    created
                )

            if self.fail_after_step == "knowledge":
                raise RuntimeError(
                    "induced migration failure"
                )

            for record in records["sql_profiles"]:
                _, created = (
                    target_sql
                    ._import_migrated_profile(
                        record,
                        scopes.target,
                    )
                )

                migrated["sql_profiles"] += int(
                    created
                )

            if self.fail_after_step == "sql":
                raise RuntimeError(
                    "induced migration failure"
                )

            path_stores = sqlite_plan.get(
                "path_stores",
                {},
            )

            if (
                sqlite_plan["tables"]
                or path_stores.get(
                    "documents"
                )
                or path_stores.get(
                    "datasets"
                )
            ):
                path_files_created = (
                    self._materialize_staged(
                        staged,
                        path_stores,
                    )
                )

                db = Database(
                    sqlite_plan["path"]
                )

                with db.tx() as con:
                    migrated[
                        "enterprise_ai_rows"
                    ] = self._sqlite_apply(
                        con,
                        sqlite_plan["tables"],
                        scopes,
                    )

                    (
                        migrated["documents"],
                        migrated["datasets"],
                        path_rows_created,
                    ) = self._path_store_apply(
                        con,
                        path_stores,
                    )

                self._verify_path_stores(
                    path_stores
                )

                if self.fail_after_step == "documents":
                    raise RuntimeError(
                        "induced document migration failure"
                    )

            self._vector_apply(
                vector_plan,
                scopes,
            )

            migrated["vector_rows"] = sum(
                1
                for item in vector_plan["rows"]
                if item[-1]
            )

            migrated["qdrant_points"] = sum(
                1
                for item in (
                    vector_plan.get(
                        "qdrant_points"
                    )
                    or []
                )
                if item["create"]
            )

            if registry_sources_changed:
                _write_source_registry(
                    source_registry["source_path"],
                    source_registry["sources"],
                )

            if registry_queries_changed:
                _write_query_registry(
                    source_registry["query_path"],
                    source_registry["queries"],
                )

            if self.fail_after_step == "enterprise_ai":
                raise RuntimeError(
                    "induced migration failure"
                )

            business_mutated = (
                any(
                    int(value) > 0
                    for value
                    in migrated.values()
                )
                or path_files_created > 0
                or path_rows_created > 0
                or registry_sources_changed
                or registry_queries_changed
            )

            result = _safe_report(
                {
                    **report,
                    "status": "MIGRATED",
                    "mutated": business_mutated,
                    "migrated": migrated,
                    "skipped": {
                        key:
                            report["found"][key]
                            - migrated[key]
                        for key in (
                            "deliverables",
                            "knowledge",
                            "sql_profiles",
                        )
                    },
                }
            )

            if self.fail_after_step == "audit":
                raise RuntimeError(
                    "induced audit failure"
                )

            evidence = self._write_evidence(
                result
            )

        except Exception as exc:
            self._restore_snapshot(
                entries
            )

            raise LegacyScopeMigrationError(
                "MIGRATION_ROLLED_BACK",
                "La migración falló y el estado previo fue restaurado",
            ) from exc

        finally:
            try:
                shutil.rmtree(
                    snapshot
                )

            except OSError as exc:
                raise LegacyScopeMigrationError(
                    "MIGRATION_CLEANUP_FAILED",
                    "No se pudo limpiar staging de migración",
                ) from exc

        return {
            **result,
            "evidence": evidence,
        }
