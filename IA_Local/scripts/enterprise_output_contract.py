from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path
from typing import Any, Dict


ENTERPRISE_OUTPUT_CONTRACT_VERSION = "r10.18c"
_FORMATS = {
    "html": {"suffix": ".html", "aliases": ("html", "dashboard", "tablero", "interactivo")},
    "pdf": {"suffix": ".pdf", "aliases": ("pdf", "reporte ejecutivo")},
    "excel": {"suffix": ".xlsx", "aliases": ("excel", "xlsx", "archivo excel", "reporte excel", "libro analitico", "hoja de calculo")},
}


class OutputContractError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _norm(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = "".join(char for char in unicodedata.normalize("NFD", text) if unicodedata.category(char) != "Mn")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", text)).strip()


def _term_pattern(term: str) -> str:
    return rf"\b{re.escape(_norm(term)).replace(r'\ ', r'\s+')}\b"


def _mentioned(text: str, aliases: tuple[str, ...]) -> bool:
    return any(re.search(_term_pattern(alias), text) for alias in aliases)


def _negated(text: str, aliases: tuple[str, ...]) -> bool:
    prefixes = (
        r"sin(?:\s+(?:archivo|reporte|salida|formato))?\s+",
        r"no\s+(?:(?:quiero|necesito|generar|generes|incluyas|incluir|crear|crees|producir|produzcas)\s+)?(?:(?:un|el|archivo|reporte|salida|formato)\s+){0,2}",
        r"(?:excluir|excluye|omite|omitir)\s+(?:(?:el|un|archivo|reporte|salida|formato)\s+){0,2}",
    )
    return any(re.search(rf"\b{prefix}{_term_pattern(alias)[2:]}", text) for alias in aliases for prefix in prefixes)


def _only_format(text: str) -> str | None:
    for kind, definition in _FORMATS.items():
        for alias in definition["aliases"]:
            pattern = rf"\bsolo\s+(?:(?:quiero|genera|generar|necesito|un|el|archivo|reporte|salida|formato)\s+){{0,3}}{_term_pattern(alias)[2:]}"
            if re.search(pattern, text):
                return kind
    return None


def compile_output_contract(prompt: str) -> Dict[str, Any]:
    text = _norm(prompt)
    only = _only_format(text)
    formats: Dict[str, Dict[str, Any]] = {}
    explicit_positive = False
    for kind, definition in _FORMATS.items():
        mentioned = _mentioned(text, definition["aliases"])
        excluded = _negated(text, definition["aliases"])
        positive = mentioned and not excluded
        explicit_positive = explicit_positive or positive
        formats[kind] = {
            "requested": bool(positive),
            "explicitly_excluded": bool(excluded),
            "reason": "explicit_exclusion" if excluded else ("explicit_request" if positive else "not_mentioned"),
        }
    if only:
        for kind in formats:
            formats[kind] = {
                "requested": kind == only,
                "explicitly_excluded": kind != only,
                "reason": "exclusive_request" if kind == only else "excluded_by_exclusive_request",
            }
    elif not explicit_positive:
        for kind in formats:
            if not formats[kind]["explicitly_excluded"]:
                formats[kind]["requested"] = True
                formats[kind]["reason"] = "default_enterprise_delivery"
    if not any(item["requested"] for item in formats.values()):
        raise OutputContractError("NO_OUTPUT_REQUESTED", "La solicitud excluye todos los formatos de salida")
    contract = {
        "schema_version": ENTERPRISE_OUTPUT_CONTRACT_VERSION,
        "status": "REQUESTED",
        "formats": formats,
        "governance": {
            "explicit_negations_have_precedence": True,
            "unrequested_outputs_forbidden": True,
            "missing_requested_outputs_fail_closed": True,
        },
    }
    contract["contract_fingerprint_sha256"] = _fingerprint(contract)
    return contract


def _fingerprint(value: Dict[str, Any]) -> str:
    unsigned = dict(value)
    unsigned.pop("contract_fingerprint_sha256", None)
    canonical = json.dumps(unsigned, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def verify_output_contract_fingerprint(contract: Any) -> str:
    if not isinstance(contract, dict):
        raise OutputContractError("OUTPUT_CONTRACT_REQUIRED", "El contrato de salidas es obligatorio")
    expected = str(contract.get("contract_fingerprint_sha256") or "").strip().lower()
    if not re.fullmatch(r"[a-f0-9]{64}", expected) or _fingerprint(contract) != expected:
        raise OutputContractError("OUTPUT_CONTRACT_INTEGRITY_MISMATCH", "El contrato de salidas fue modificado")
    return expected


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def finalize_output_contract(
    requested_contract: Dict[str, Any],
    outputs: Dict[str, Any],
    artifacts_root: Path,
) -> Dict[str, Any]:
    verify_output_contract_fingerprint(requested_contract)
    root = Path(artifacts_root).resolve()
    formats: Dict[str, Dict[str, Any]] = {}
    missing = []
    for kind, definition in _FORMATS.items():
        requested = bool((requested_contract.get("formats", {}).get(kind) or {}).get("requested"))
        filename = str(outputs.get(kind) or "").strip()
        if not requested and filename:
            raise OutputContractError("UNREQUESTED_OUTPUT_GENERATED", f"Se generó una salida {kind} no autorizada")
        if not requested:
            formats[kind] = {"status": "NOT_REQUESTED", "filename": None, "sha256": None, "size_bytes": None}
            continue
        if not filename:
            formats[kind] = {"status": "BLOCKED", "reason": "requested_output_not_generated", "filename": None, "sha256": None, "size_bytes": None}
            missing.append(kind)
            continue
        if Path(filename).name != filename or Path(filename).suffix.lower() != definition["suffix"]:
            raise OutputContractError("INVALID_OUTPUT_ARTIFACT", f"El artefacto {kind} no es válido")
        path = (root / filename).resolve()
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise OutputContractError("OUTPUT_BOUNDARY_VIOLATION", f"El artefacto {kind} sale del directorio de reportes") from exc
        if not path.is_file():
            formats[kind] = {"status": "BLOCKED", "reason": "requested_output_missing", "filename": filename, "sha256": None, "size_bytes": None}
            missing.append(kind)
            continue
        formats[kind] = {"status": "GENERATED", "filename": filename, "sha256": _sha256_file(path), "size_bytes": path.stat().st_size}
    completed = {
        "schema_version": ENTERPRISE_OUTPUT_CONTRACT_VERSION,
        "status": "BLOCKED" if missing else "COMPLETE",
        "requested_contract_fingerprint_sha256": requested_contract["contract_fingerprint_sha256"],
        "formats": formats,
        "missing_requested_formats": missing,
        "governance": dict(requested_contract.get("governance") or {}),
    }
    completed["contract_fingerprint_sha256"] = _fingerprint(completed)
    if missing:
        raise OutputContractError("REQUESTED_OUTPUT_MISSING", "Faltan salidas solicitadas: " + ", ".join(missing))
    return completed
