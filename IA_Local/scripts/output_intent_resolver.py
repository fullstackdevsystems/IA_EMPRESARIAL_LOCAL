from __future__ import annotations
import re
import unicodedata
from typing import Dict, List

OUTPUT_INTENT_RESOLVER_VERSION = "r10.18c"

def _norm(text: str) -> str:
    value = str(text or "").strip().lower()
    value = "".join(c for c in unicodedata.normalize("NFD", value) if unicodedata.category(c) != "Mn")
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()

def _mentioned(n: str, kind: str) -> bool:
    patterns = {
        "html": [r"\bhtml\b", r"\bdashboard\b", r"\btablero\b", r"\binteractiv[oa]\b", r"\bbusiness intelligence\b", r"\bpower bi\b"],
        "pdf": [r"\bpdf\b", r"\breporte ejecutivo\b", r"\binforme ejecutivo\b", r"\bdocumento ejecutivo\b"],
        "excel": [r"\bexcel\b", r"\bxlsx\b", r"\blibro de excel\b", r"\barchivo de excel\b", r"\bhoja de calculo\b", r"\blibro analitico\b"],
    }.get(kind, [])
    return any(re.search(p, n) for p in patterns)

def _negated(n: str, kind: str) -> bool:
    aliases = {
        "html": ["html", "dashboard", "tablero"],
        "pdf": ["pdf", "reporte ejecutivo", "informe ejecutivo"],
        "excel": ["excel", "xlsx", "libro de excel", "archivo de excel"],
    }[kind]
    for alias in aliases:
        a = re.escape(_norm(alias))
        patterns = [
            rf"\bsin\s+(?:un\s+|el\s+|archivo\s+)?{a}\b",
            rf"\bno\s+(?:quiero|generar|generes|genera|incluyas|incluir|necesito|crear|crees|exportar|exportes)?\s*(?:un\s+|el\s+|archivo\s+)?{a}\b",
            rf"\bexcluir\s+(?:un\s+|el\s+)?{a}\b",
            rf"\bomitir\s+(?:un\s+|el\s+)?{a}\b",
            rf"\bomite\s+(?:un\s+|el\s+)?{a}\b",
        ]
        if any(re.search(p, n) for p in patterns):
            return True
    return False

def resolve_output_intent(prompt: str, *, default_all: bool = True) -> Dict[str, object]:
    n = _norm(prompt)
    outputs = {"html": False, "pdf": False, "excel": False}

    solo_map = {
        "pdf": r"\bsolo\s+(?:quiero\s+|genera\s+|generar\s+|un\s+|el\s+|archivo\s+)*pdf\b",
        "excel": r"\bsolo\s+(?:quiero\s+|genera\s+|generar\s+|un\s+|el\s+|archivo\s+)*(?:excel|xlsx)\b",
        "html": r"\bsolo\s+(?:quiero\s+|genera\s+|generar\s+|un\s+|el\s+|archivo\s+)*(?:html|dashboard|tablero)\b",
    }
    for kind, pattern in solo_map.items():
        if re.search(pattern, n):
            outputs[kind] = True
            return {"schema_version": OUTPUT_INTENT_RESOLVER_VERSION, "outputs": outputs, "requested": [kind], "explicit": True, "reason": f"explicit_only_{kind}"}

    all_formats = bool(re.search(r"\b(?:los\s+)?tres\s+(?:formatos|salidas|entregables|archivos)\b", n))
    if all_formats:
        outputs = {"html": True, "pdf": True, "excel": True}
    else:
        for kind in outputs:
            if _mentioned(n, kind):
                outputs[kind] = True

    for kind in outputs:
        if _negated(n, kind):
            outputs[kind] = False

    explicit = any(_mentioned(n, k) for k in outputs) or all_formats
    if not any(outputs.values()) and not explicit and default_all:
        outputs = {"html": True, "pdf": True, "excel": True}

    requested = [k for k, v in outputs.items() if v]
    return {"schema_version": OUTPUT_INTENT_RESOLVER_VERSION, "outputs": outputs, "requested": requested, "explicit": explicit, "reason": "resolved_from_prompt" if explicit else "default_all"}

def output_list(prompt: str, *, default_all: bool = True) -> List[str]:
    return list(resolve_output_intent(prompt, default_all=default_all)["requested"])
