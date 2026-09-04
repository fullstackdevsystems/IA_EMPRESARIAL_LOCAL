from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from enterprise_tenant_registry import EnterpriseTenantRegistry, assert_tenant_active


ENTERPRISE_DELIVERABLE_REGISTRY_VERSION = "r10.18b"
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$")
_FORMATS = {"html": ".html", "excel": ".xlsx", "pdf": ".pdf"}


class DeliverableRegistryError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _canonical(value: Dict[str, Any]) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_id(value: Any, field: str) -> str:
    text = str(value or "").strip()
    if not _SAFE_ID.fullmatch(text) or text in {".", ".."}:
        raise DeliverableRegistryError("INVALID_IDENTIFIER", f"{field} no es un identificador seguro")
    return text


def normalize_deliverable_scope(scope: Any) -> Dict[str, Optional[str]]:
    if not isinstance(scope, dict):
        raise DeliverableRegistryError("SCOPE_REQUIRED", "El scope explícito es obligatorio")
    allowed = {"company_id", "user_id", "business_unit", "branch"}
    if set(scope) - allowed:
        raise DeliverableRegistryError("INVALID_SCOPE", "El scope contiene campos no permitidos")
    normalized: Dict[str, Optional[str]] = {
        "company_id": _safe_id(scope.get("company_id"), "company_id"),
        "user_id": _safe_id(scope.get("user_id"), "user_id"),
        "business_unit": None,
        "branch": None,
    }
    for key in ("business_unit", "branch"):
        value = scope.get(key)
        normalized[key] = _safe_id(value, key) if value not in (None, "") else None
    return normalized


def verify_manifest_fingerprint(manifest: Any) -> str:
    if not isinstance(manifest, dict):
        raise DeliverableRegistryError("MANIFEST_REQUIRED", "El manifiesto gobernado es obligatorio")
    expected = str(manifest.get("manifest_fingerprint_sha256") or "").strip().lower()
    if not re.fullmatch(r"[a-f0-9]{64}", expected):
        raise DeliverableRegistryError("INVALID_MANIFEST_FINGERPRINT", "Fingerprint de manifiesto inválido")
    unsigned = dict(manifest)
    unsigned.pop("manifest_fingerprint_sha256", None)
    actual = hashlib.sha256(_canonical(unsigned)).hexdigest()
    if actual != expected:
        raise DeliverableRegistryError("MANIFEST_INTEGRITY_MISMATCH", "El manifiesto fue modificado")
    return expected


class GovernedDeliverableRegistry:
    def __init__(self, artifacts_root: Path, registry_root: Optional[Path] = None, tenant_registry: Optional[EnterpriseTenantRegistry] = None):
        self.artifacts_root = Path(artifacts_root)
        self.registry_root = Path(registry_root) if registry_root is not None else self.artifacts_root / ".registry"
        self.tenant_registry = tenant_registry

    def _roots(self) -> tuple[Path, Path]:
        self.artifacts_root.mkdir(parents=True, exist_ok=True)
        self.registry_root.mkdir(parents=True, exist_ok=True)
        artifacts = self.artifacts_root.resolve()
        registry = self.registry_root.resolve()
        try:
            registry.relative_to(artifacts)
        except ValueError as exc:
            raise DeliverableRegistryError("REGISTRY_BOUNDARY_VIOLATION", "El registro debe permanecer dentro del directorio de reportes") from exc
        return artifacts, registry

    def _scope_dir(self, scope: Dict[str, Optional[str]], create: bool) -> Path:
        assert_tenant_active(scope, self.tenant_registry)
        _, registry = self._roots()
        parts = [scope["company_id"], scope["user_id"], scope.get("business_unit") or "_", scope.get("branch") or "_"]
        target = registry.joinpath(*[str(part) for part in parts])
        if create:
            target.mkdir(parents=True, exist_ok=True)
        resolved = target.resolve()
        try:
            resolved.relative_to(registry)
        except ValueError as exc:
            raise DeliverableRegistryError("SCOPE_BOUNDARY_VIOLATION", "El scope sale del registro") from exc
        return resolved

    def _record_path(self, scope: Dict[str, Optional[str]], run_id: str, create_dir: bool = False) -> Path:
        safe_run = _safe_id(run_id, "run_id")
        return self._scope_dir(scope, create_dir) / f"{safe_run}.json"

    def _artifact(self, kind: str, filename: Any) -> Dict[str, Any]:
        artifacts, _ = self._roots()
        name = str(filename or "").strip()
        if kind not in _FORMATS or not name or Path(name).name != name or Path(name).suffix.lower() != _FORMATS[kind]:
            raise DeliverableRegistryError("INVALID_ARTIFACT", f"Artefacto {kind} inválido")
        candidate = (artifacts / name).resolve()
        try:
            candidate.relative_to(artifacts)
        except ValueError as exc:
            raise DeliverableRegistryError("ARTIFACT_BOUNDARY_VIOLATION", "El artefacto sale del directorio de reportes") from exc
        if not candidate.is_file():
            raise DeliverableRegistryError("ARTIFACT_NOT_FOUND", f"No existe el artefacto {kind}")
        return {"format": kind, "filename": name, "size_bytes": candidate.stat().st_size, "sha256": _sha256_file(candidate)}

    def register(
        self,
        *,
        scope: Dict[str, Any],
        run_id: str,
        manifest: Dict[str, Any],
        outputs: Dict[str, Any],
        domain: Optional[str] = None,
    ) -> Dict[str, Any]:
        normalized_scope = normalize_deliverable_scope(scope)
        safe_run = _safe_id(run_id, "run_id")
        manifest_fingerprint = verify_manifest_fingerprint(manifest)
        if str(manifest.get("status") or "").strip().upper() != "READY":
            raise DeliverableRegistryError(
                "MANIFEST_NOT_READY",
                "No se puede registrar una ejecución cuyo manifiesto no está READY",
            )

        request = manifest.get("request") if isinstance(manifest.get("request"), dict) else {}
        source = manifest.get("source") if isinstance(manifest.get("source"), dict) else {}
        governance = manifest.get("governance") if isinstance(manifest.get("governance"), dict) else {}

        source_fingerprint = str(source.get("source_fingerprint_sha256") or "").strip().lower()
        if governance.get("source_fingerprint_required") is True:
            if not re.fullmatch(r"[a-f0-9]{64}", source_fingerprint):
                raise DeliverableRegistryError(
                    "SOURCE_FINGERPRINT_REQUIRED",
                    "La ejecución gobernada requiere fingerprint SHA-256 de la fuente",
                )

        deliverables = [self._artifact(kind, outputs[kind]) for kind in _FORMATS if outputs.get(kind)]
        if not deliverables:
            raise DeliverableRegistryError("DELIVERABLE_REQUIRED", "La ejecución no produjo entregables")

        if governance.get("output_intent_enforced") is True:
            requested = request.get("requested_formats")
            if not isinstance(requested, list):
                raise DeliverableRegistryError(
                    "OUTPUT_INTENT_REQUIRED",
                    "El manifiesto gobernado requiere formatos solicitados",
                )
            requested_set = {str(item).strip().lower() for item in requested if str(item or "").strip()}
            if not requested_set or not requested_set.issubset(set(_FORMATS)):
                raise DeliverableRegistryError(
                    "INVALID_OUTPUT_INTENT",
                    "Los formatos solicitados del manifiesto son inválidos",
                )
            produced_set = {str(item.get("format") or "") for item in deliverables}
            if produced_set != requested_set:
                raise DeliverableRegistryError(
                    "OUTPUT_INTENT_MISMATCH",
                    "Los entregables producidos no coinciden con la intención de salida gobernada",
                )
        record: Dict[str, Any] = {
            "schema_version": ENTERPRISE_DELIVERABLE_REGISTRY_VERSION,
            "status": "READY",
            "run_id": safe_run,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "scope": normalized_scope,
            "domain": str(domain or "").strip() or None,
            "prompt_sha256": request.get("prompt_sha256"),
            "source_fingerprint_sha256": source.get("source_fingerprint_sha256"),
            "manifest_fingerprint_sha256": manifest_fingerprint,
            "deliverables": deliverables,
            "governance": {
                "read_only": True,
                "scope_enforced": True,
                "artifact_boundary_enforced": True,
                "integrity_verified_on_read": True,
                "paths_serialized": False,
                "credentials_serialized": False,
                "integrity_closure_version": "r10.18d",
                "manifest_ready_required": True,
                "output_intent_verified": bool(governance.get("output_intent_enforced")),
                "source_fingerprint_verified": bool(governance.get("source_fingerprint_required")),
            },
        }
        record["record_fingerprint_sha256"] = hashlib.sha256(_canonical(record)).hexdigest()
        target = self._record_path(normalized_scope, safe_run, create_dir=True)
        if target.exists():
            raise DeliverableRegistryError("RUN_ALREADY_EXISTS", "La ejecución ya está registrada")
        temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
        try:
            temporary.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
            try:
                os.link(temporary, target)
            except FileExistsError as exc:
                raise DeliverableRegistryError("RUN_ALREADY_EXISTS", "La ejecución ya está registrada") from exc
        finally:
            if temporary.exists():
                temporary.unlink()
        return dict(record)

    def get(self, scope: Dict[str, Any], run_id: str, verify_artifacts: bool = True) -> Dict[str, Any]:
        normalized_scope = normalize_deliverable_scope(scope)
        path = self._record_path(normalized_scope, run_id)
        if not path.is_file():
            raise DeliverableRegistryError("RUN_NOT_FOUND", "La ejecución no existe en este scope")
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise DeliverableRegistryError("INVALID_RECORD", "El registro no es legible") from exc
        expected = str(record.get("record_fingerprint_sha256") or "").lower()
        unsigned = dict(record)
        unsigned.pop("record_fingerprint_sha256", None)
        if not re.fullmatch(r"[a-f0-9]{64}", expected) or hashlib.sha256(_canonical(unsigned)).hexdigest() != expected:
            raise DeliverableRegistryError("RECORD_INTEGRITY_MISMATCH", "El registro fue modificado")
        if record.get("scope") != normalized_scope or record.get("run_id") != _safe_id(run_id, "run_id"):
            raise DeliverableRegistryError("SCOPE_MISMATCH", "El registro no pertenece al scope solicitado")
        if verify_artifacts:
            for item in list(record.get("deliverables") or []):
                current = self._artifact(str(item.get("format") or ""), item.get("filename"))
                if current["sha256"] != item.get("sha256") or current["size_bytes"] != item.get("size_bytes"):
                    raise DeliverableRegistryError("ARTIFACT_INTEGRITY_MISMATCH", "Un entregable fue modificado")
        return record

    def list(self, scope: Dict[str, Any], limit: int = 100) -> List[Dict[str, Any]]:
        normalized_scope = normalize_deliverable_scope(scope)
        if isinstance(limit, bool) or not isinstance(limit, int):
            raise DeliverableRegistryError("INVALID_LIMIT", "limit debe ser entero")
        limit = max(1, min(limit, 500))
        directory = self._scope_dir(normalized_scope, create=False)
        if not directory.exists():
            return []
        records = []
        for path in sorted(directory.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
            records.append(self.get(normalized_scope, path.stem, verify_artifacts=True))
            if len(records) >= limit:
                break
        return records

    def artifact_path(self, scope: Dict[str, Any], run_id: str, kind: str) -> Path:
        record = self.get(scope, run_id, verify_artifacts=True)
        for item in record["deliverables"]:
            if item.get("format") == kind:
                artifacts, _ = self._roots()
                return (artifacts / item["filename"]).resolve()
        raise DeliverableRegistryError("ARTIFACT_NOT_FOUND", "El formato no existe en esta ejecución")


def deliverable_registry_public_audit(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    formats = sorted({item.get("format") for record in records for item in list(record.get("deliverables") or []) if item.get("format")})
    return {
        "schema_version": ENTERPRISE_DELIVERABLE_REGISTRY_VERSION,
        "status": "READY",
        "run_count": len(records),
        "formats": formats,
        "scope_enforced": True,
        "integrity_verified_on_read": True,
        "paths_serialized": False,
        "credentials_serialized": False,
    }
