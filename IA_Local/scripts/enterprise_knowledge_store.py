from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from enterprise_deliverable_registry import normalize_deliverable_scope
from enterprise_tenant_registry import EnterpriseTenantRegistry, assert_tenant_active


ENTERPRISE_KNOWLEDGE_STORE_VERSION = "r10.19b"
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$")
_TYPES = {
    "document_fact", "definition", "business_term", "analysis_summary",
    "governed_note", "prior_result", "semantic_mapping",
    "approved_rule_reference",
}
_STATUSES = {"ACTIVE", "INVALIDATED", "SUPERSEDED"}
_QUERY_STOPWORDS = {
    "a", "al", "cual", "como", "con", "de", "del", "el", "en", "es",
    "esta", "este", "la", "las", "lo", "los", "que", "que", "por", "para",
    "significa", "son", "un", "una", "y",
}


class EnterpriseKnowledgeError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _canonical(value: Dict[str, Any]) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _norm(value: Any) -> str:
    text = unicodedata.normalize("NFD", str(value or "").lower())
    text = "".join(char for char in text if unicodedata.category(char) != "Mn")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9_]+", " ", text)).strip()


def _safe_id(value: Any) -> str:
    text = str(value or "").strip()
    if not _SAFE_ID.fullmatch(text) or text in {".", ".."}:
        raise EnterpriseKnowledgeError("INVALID_KNOWLEDGE_ID", "knowledge_id no es seguro")
    return text


def _fingerprint(record: Dict[str, Any]) -> str:
    unsigned = dict(record)
    unsigned.pop("fingerprint_sha256", None)
    return hashlib.sha256(_canonical(unsigned)).hexdigest()


class EnterpriseKnowledgeStore:
    """Registro local, determinista y aislado por scope para conocimiento gobernado."""

    def __init__(self, root: Path, tenant_registry: Optional[EnterpriseTenantRegistry] = None):
        self.root = Path(root)
        self.tenant_registry = tenant_registry

    def _scope_dir(self, scope: Dict[str, Any], create: bool = False) -> Path:
        normalized = normalize_deliverable_scope(scope)
        assert_tenant_active(normalized, self.tenant_registry)
        if create:
            self.root.mkdir(parents=True, exist_ok=True)
        root = self.root.resolve()
        parts = [normalized["company_id"], normalized["user_id"], normalized.get("business_unit") or "_", normalized.get("branch") or "_"]
        target = root.joinpath(*parts)
        if create:
            target.mkdir(parents=True, exist_ok=True)
        resolved = target.resolve()
        try:
            resolved.relative_to(root)
        except ValueError as exc:
            raise EnterpriseKnowledgeError("SCOPE_BOUNDARY_VIOLATION", "El scope sale del knowledge store") from exc
        return resolved

    def _path(self, scope: Dict[str, Any], knowledge_id: Any, create: bool = False) -> Path:
        return self._scope_dir(scope, create) / f"{_safe_id(knowledge_id)}.json"

    def _read(self, path: Path) -> Dict[str, Any]:
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise EnterpriseKnowledgeError("KNOWLEDGE_RECORD_INVALID", "No se pudo leer el record de conocimiento") from exc
        if not isinstance(record, dict) or _fingerprint(record) != str(record.get("fingerprint_sha256") or ""):
            raise EnterpriseKnowledgeError("KNOWLEDGE_INTEGRITY_MISMATCH", "El record de conocimiento fue modificado")
        return record

    def _write(self, path: Path, record: Dict[str, Any]) -> Dict[str, Any]:
        record["fingerprint_sha256"] = _fingerprint(record)
        tmp = path.with_suffix(".tmp")
        tmp.write_bytes(_canonical(record))
        tmp.replace(path)
        return dict(record)

    def register_knowledge(
        self, *, scope: Dict[str, Any], knowledge_id: str, knowledge_type: str,
        title: str, content: str, source: Dict[str, Any], provenance: Dict[str, Any],
        confidence: Optional[float] = None, tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        normalized = normalize_deliverable_scope(scope)
        path = self._path(normalized, knowledge_id, create=True)
        if path.exists():
            raise EnterpriseKnowledgeError("KNOWLEDGE_ALREADY_EXISTS", "knowledge_id ya existe en el scope")
        kind = str(knowledge_type or "").strip()
        if kind not in _TYPES:
            raise EnterpriseKnowledgeError("INVALID_KNOWLEDGE_TYPE", "knowledge_type no está permitido")
        if not str(title or "").strip() or not str(content or "").strip():
            raise EnterpriseKnowledgeError("KNOWLEDGE_CONTENT_REQUIRED", "title y content son obligatorios")
        if not isinstance(source, dict) or not str(source.get("source") or "").strip():
            raise EnterpriseKnowledgeError("KNOWLEDGE_SOURCE_REQUIRED", "source.source es obligatorio")
        if not isinstance(provenance, dict) or not str(provenance.get("origin") or "").strip():
            raise EnterpriseKnowledgeError("KNOWLEDGE_PROVENANCE_REQUIRED", "provenance.origin es obligatorio")
        if confidence is not None and (isinstance(confidence, bool) or not 0 <= float(confidence) <= 1):
            raise EnterpriseKnowledgeError("INVALID_CONFIDENCE", "confidence debe estar entre 0 y 1")
        now = datetime.now(timezone.utc).isoformat()
        record: Dict[str, Any] = {
            "schema_version": ENTERPRISE_KNOWLEDGE_STORE_VERSION,
            "knowledge_id": _safe_id(knowledge_id), "scope": normalized,
            "knowledge_type": kind, "title": str(title).strip(), "content": str(content).strip(),
            "source": dict(source), "provenance": dict(provenance), "status": "ACTIVE",
            "created_at": now, "updated_at": now, "version": 1,
            "confidence": float(confidence) if confidence is not None else None,
            "tags": [str(tag).strip() for tag in list(tags or []) if str(tag).strip()],
        }
        return self._write(path, record)

    def get(self, scope: Dict[str, Any], knowledge_id: str) -> Dict[str, Any]:
        path = self._path(scope, knowledge_id)
        if not path.is_file():
            raise EnterpriseKnowledgeError("KNOWLEDGE_NOT_FOUND", "No existe conocimiento para ese scope")
        return self._read(path)

    def list(self, scope: Dict[str, Any], *, include_inactive: bool = False) -> List[Dict[str, Any]]:
        directory = self._scope_dir(scope)
        if not directory.exists():
            return []
        records = [self._read(path) for path in sorted(directory.glob("*.json"))]
        return records if include_inactive else [record for record in records if record.get("status") == "ACTIVE"]

    def search(self, scope: Dict[str, Any], query: str, *, knowledge_type: Optional[str] = None) -> List[Dict[str, Any]]:
        tokens = {
            token for token in _norm(query).split()
            if len(token) >= 3 and token not in _QUERY_STOPWORDS
        }
        if not tokens:
            return []
        matches = []
        for record in self.list(scope):
            if knowledge_type and record.get("knowledge_type") != knowledge_type:
                continue
            haystack = _norm(" ".join([record.get("title", ""), record.get("content", ""), " ".join(record.get("tags") or [])]))
            score = len(tokens & set(haystack.split()))
            if score:
                matches.append({**record, "relevance": {"score": score}})
        return sorted(matches, key=lambda item: (-item["relevance"]["score"], item["knowledge_id"]))

    def invalidate(self, scope: Dict[str, Any], knowledge_id: str, *, reason: str, actor: str) -> Dict[str, Any]:
        path = self._path(scope, knowledge_id)
        record = self.get(scope, knowledge_id)
        if record.get("status") != "ACTIVE":
            raise EnterpriseKnowledgeError("KNOWLEDGE_NOT_ACTIVE", "Solo conocimiento ACTIVE puede invalidarse")
        if not str(reason or "").strip() or not str(actor or "").strip():
            raise EnterpriseKnowledgeError("INVALIDATION_PROVENANCE_REQUIRED", "reason y actor son obligatorios")
        record["status"] = "INVALIDATED"
        record["version"] = int(record.get("version") or 0) + 1
        record["updated_at"] = datetime.now(timezone.utc).isoformat()
        record["invalidation"] = {"reason": str(reason).strip(), "actor": str(actor).strip(), "at": record["updated_at"]}
        return self._write(path, record)
