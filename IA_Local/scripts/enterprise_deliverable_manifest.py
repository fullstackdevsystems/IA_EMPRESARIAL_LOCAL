from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Optional


ENTERPRISE_DELIVERABLE_MANIFEST_VERSION = "r10.18a"
_ENTERPRISE_AUDITS = (
    "enterprise_memory_closure",
    "enterprise_source_registry",
    "enterprise_file_connector",
    "enterprise_sql_server_connector",
    "enterprise_source_execution",
    "enterprise_query_registry",
)


def _text(value: Any) -> Optional[str]:
    text = str(value or "").strip()
    return text or None


def _strings(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item or "").strip()]


def _component(item: Dict[str, Any]) -> Dict[str, Any]:
    provenance = item.get("provenance") if isinstance(item.get("provenance"), dict) else {}
    return {
        "component_id": _text(item.get("id")),
        "type": _text(item.get("type")),
        "title": _text(item.get("title")),
        "status": _text(item.get("status")),
        "semantic_role": _text(item.get("semantic_role")),
        "formula": _text(item.get("formula")),
        "dependencies": _strings(item.get("dependencies")),
        "source_columns": _strings(item.get("source_columns")),
        "reason": _text(item.get("reason")),
        "provenance_source": _text(provenance.get("source")),
        "provenance_confidence": provenance.get("confidence"),
        "business_rule_id": _text(provenance.get("business_rule_id") or provenance.get("rule_id")),
    }


def build_governed_deliverable_manifest(
    *,
    dashboard_plan: Dict[str, Any],
    filename: str,
    sheet: str = "",
    row_count: Optional[int] = None,
    prompt_sha256: Optional[str] = None,
    source_fingerprint_sha256: Optional[str] = None,
) -> Dict[str, Any]:
    execution = dashboard_plan.get("execution_plan") if isinstance(dashboard_plan, dict) else None
    execution = execution if isinstance(execution, dict) else {}
    spec = execution.get("dashboard_spec") if isinstance(execution.get("dashboard_spec"), dict) else {}
    components = [
        _component(item)
        for item in list(spec.get("components") or [])
        if isinstance(item, dict)
    ]
    counts = {status: sum(1 for item in components if item.get("status") == status) for status in ("SUPPORTED", "DERIVABLE", "BLOCKED")}
    audits = []
    for key in _ENTERPRISE_AUDITS:
        value = spec.get(key)
        if not isinstance(value, dict):
            continue
        audits.append({
            "capability": key,
            "schema_version": _text(value.get("schema_version")),
            "status": _text(value.get("status")),
            "fingerprint_sha256": _text(value.get("fingerprint_sha256")),
        })
    source = spec.get("source") if isinstance(spec.get("source"), dict) else {}
    manifest = {
        "schema_version": ENTERPRISE_DELIVERABLE_MANIFEST_VERSION,
        "status": "READY" if spec else "BLOCKED",
        "reason": None if spec else "governed_dashboard_spec_required",
        "source": {
            "filename": str(filename or ""),
            "sheet": str(sheet or ""),
            "row_count": int(row_count) if row_count is not None else None,
            "source_fingerprint_sha256": _text(source_fingerprint_sha256 or source.get("fingerprint_sha256")),
        },
        "request": {
            "prompt_sha256": _text(prompt_sha256 or dashboard_plan.get("request_prompt_sha256")),
            "prompt_integrity": _text(dashboard_plan.get("prompt_integrity")),
        },
        "authority": {
            "source_of_truth": _text(execution.get("source_of_truth")),
            "execution_plan_version": _text(execution.get("version")),
            "dashboard_spec_version": _text(spec.get("schema_version")),
            "ruleset_version": _text((spec.get("provenance") or {}).get("ruleset_version")) if isinstance(spec.get("provenance"), dict) else None,
        },
        "summary": {
            "component_count": len(components),
            "supported_count": counts["SUPPORTED"],
            "derivable_count": counts["DERIVABLE"],
            "blocked_count": counts["BLOCKED"],
            "coverage_pct": execution.get("coverage_pct"),
        },
        "components": components,
        "governance_audits": audits,
        "governance": {
            "same_authority_for_all_formats": True,
            "blocked_components_are_not_rendered_as_values": True,
            "raw_rows_serialized": False,
            "sql_serialized": False,
            "credentials_serialized": False,
        },
    }
    canonical = json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    manifest["manifest_fingerprint_sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return manifest


def deliverable_manifest_summary_rows(manifest: Dict[str, Any]) -> List[Dict[str, Any]]:
    source = manifest.get("source") if isinstance(manifest.get("source"), dict) else {}
    request = manifest.get("request") if isinstance(manifest.get("request"), dict) else {}
    authority = manifest.get("authority") if isinstance(manifest.get("authority"), dict) else {}
    summary = manifest.get("summary") if isinstance(manifest.get("summary"), dict) else {}
    pairs = [
        ("Versión del manifiesto", manifest.get("schema_version")),
        ("Estado", manifest.get("status")),
        ("Archivo", source.get("filename")),
        ("Hoja", source.get("sheet")),
        ("Filas", source.get("row_count")),
        ("Prompt SHA-256", request.get("prompt_sha256")),
        ("Integridad del prompt", request.get("prompt_integrity")),
        ("Fuente de autoridad", authority.get("source_of_truth")),
        ("Versión del plan", authority.get("execution_plan_version")),
        ("Versión del dashboard spec", authority.get("dashboard_spec_version")),
        ("Versión de reglas", authority.get("ruleset_version")),
        ("Componentes", summary.get("component_count")),
        ("SUPPORTED", summary.get("supported_count")),
        ("DERIVABLE", summary.get("derivable_count")),
        ("BLOCKED", summary.get("blocked_count")),
        ("Cobertura %", summary.get("coverage_pct")),
        ("Fingerprint del manifiesto", manifest.get("manifest_fingerprint_sha256")),
    ]
    return [{"Campo": key, "Valor": value} for key, value in pairs]


def deliverable_manifest_component_rows(manifest: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = []
    for item in list(manifest.get("components") or []):
        if not isinstance(item, dict):
            continue
        rows.append({
            "Componente": item.get("component_id"),
            "Tipo": item.get("type"),
            "Título": item.get("title"),
            "Estado": item.get("status"),
            "Rol semántico": item.get("semantic_role"),
            "Fórmula": item.get("formula"),
            "Dependencias": ", ".join(_strings(item.get("dependencies"))),
            "Columnas fuente": ", ".join(_strings(item.get("source_columns"))),
            "Motivo": item.get("reason"),
            "Provenance": item.get("provenance_source"),
            "Confianza": item.get("provenance_confidence"),
            "Regla": item.get("business_rule_id"),
        })
    return rows
