from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, List, Optional

import pandas as pd


def _norm(v: Any) -> str:
    s = str(v or "").strip().lower()
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    s = re.sub(r"[^a-z0-9%]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


ALIASES = {
    "customer": ["cliente", "customer", "razon social"],
    "customer_id": ["cod cliente", "cod_cliente", "codigo cliente", "customer id", "customerid"],
    "product": ["articulo", "producto", "product", "descripcion"],
    "seller": ["vendedor", "ejecutivo", "asesor", "seller"],
    "zone": ["zona", "region", "territorio"],
    "category": ["categoria", "category", "familia"],
    "line": ["cod linea", "cod_linea", "linea"],
    "actual": ["toneladas vendidas actual", "toneladas_vendidas_actual", "venta actual", "ventas actuales", "actual"],
    "budget": ["toneladas vendidas presupuesto", "toneladas_vendidas_presupuesto", "presupuesto", "budget"],
    "previous": ["toneladas vendidas anterior", "toneladas_vendidas_anterior", "venta anterior", "ventas anteriores", "anterior", "previous"],
    "revenue": ["importe venta", "importe_venta", "venta neta", "ventas netas", "revenue", "total venta"],
    "quantity": ["toneladas vendidas", "toneladas_vendidas", "cantidad", "unidades", "quantity", "qty"],
    "profit": ["utilidad", "ganancia", "profit"],
    "cost": ["costo", "coste", "cost"],
    "date": ["fecha", "date", "fecha venta", "fecha factura"],
}


def strict_semantic_columns(df: pd.DataFrame) -> Dict[str, Optional[str]]:
    nmap = {_norm(c): str(c) for c in df.columns}
    out: Dict[str, Optional[str]] = {}
    for role, aliases in ALIASES.items():
        found = None
        # 1) exact normalized match
        for a in aliases:
            na = _norm(a)
            if na in nmap:
                found = nmap[na]
                break
        # 2) conservative contains: alias must be contained in the real column,
        # never the reverse. This prevents "Toneladas_Vendidas" from being treated
        # as "Toneladas_Vendidas_Presupuesto" or "..._Anterior".
        if found is None:
            for a in sorted((_norm(x) for x in aliases), key=len, reverse=True):
                if len(a) < 5:
                    continue
                for nc, orig in nmap.items():
                    if a in nc:
                        found = orig
                        break
                if found:
                    break
        out[role] = found
    return out


def _has_any(p: str, terms: List[str]) -> bool:
    return any(_norm(t) in p for t in terms)


def requested_intents(prompt: str) -> List[str]:
    p = _norm(prompt)
    intents: List[str] = []
    rules = [
        ("lost_customers", ["clientes perdidos", "cliente perdido", "clientes inactivos", "clientes que se perdieron"]),
        ("recovered_customers", ["clientes recuperados", "recuperacion de clientes", "recuperados"]),
        ("budget", ["presupuesto", "budget"]),
        ("compliance", ["cumplimiento", "cumplimiento presupuestal", "cumplimiento de presupuesto"]),
        ("previous_comparison", ["periodo anterior", "anterior", "variacion", "comparar contra anterior"]),
        ("risks", ["riesgos", "riesgo"]),
        ("opportunities", ["oportunidades", "oportunidad"]),
    ]
    for name, terms in rules:
        if _has_any(p, terms):
            intents.append(name)
    return intents


def _requirements_for_intent(intent: str) -> List[str]:
    return {
        "lost_customers": ["customer", "actual", "previous"],
        "recovered_customers": ["customer", "actual", "previous"],
        "budget": ["budget"],
        "compliance": ["actual", "budget"],
        "previous_comparison": ["actual", "previous"],
        "risks": [],
        "opportunities": [],
    }.get(intent, [])


def _unsupported(intents: List[str], sem: Dict[str, Optional[str]]) -> Dict[str, List[str]]:
    missing: Dict[str, List[str]] = {}
    for intent in intents:
        req = _requirements_for_intent(intent)
        miss = [r for r in req if not sem.get(r)]
        if miss:
            missing[intent] = miss
    return missing


def _mentions_budget(text: str) -> bool:
    p = _norm(text)
    return "presupuesto" in p or "budget" in p or "cumplimiento" in p


def _mentions_previous(text: str) -> bool:
    p = _norm(text)
    return "anterior" in p or "variacion" in p or "perdido" in p or "recuper" in p


def _same_nonempty(*xs: Any) -> bool:
    vals = [x for x in xs if x]
    return len(vals) >= 2 and len(set(vals)) < len(vals)


def _safe_filters(df: pd.DataFrame, sem: Dict[str, Optional[str]]) -> List[Dict[str, str]]:
    out = []
    for role in ("customer", "seller", "product", "zone", "category", "line"):
        c = sem.get(role)
        if c and c in df.columns and int(df[c].nunique(dropna=True)) <= 500:
            out.append({"column": c, "label": str(c).replace("_", " ")})
    return out[:8]


def _safe_table(df: pd.DataFrame, sem: Dict[str, Optional[str]]) -> Dict[str, Any]:
    cols: List[str] = []
    for role in ("customer", "seller", "product", "zone", "category", "quantity", "revenue", "profit", "cost", "date"):
        c = sem.get(role)
        if c and c in df.columns and c not in cols:
            cols.append(c)
    if not cols:
        cols = [str(c) for c in df.columns[:10]]
    return {"title": "Datos disponibles", "columns": cols[:12], "limit": 100}


def _intent_label(intent: str) -> str:
    return {
        "lost_customers": "clientes perdidos",
        "recovered_customers": "recuperación de clientes",
        "budget": "presupuesto",
        "compliance": "cumplimiento contra presupuesto",
        "previous_comparison": "comparación contra periodo anterior",
        "risks": "riesgos",
        "opportunities": "oportunidades",
    }.get(intent, intent)


def _role_label(role: str) -> str:
    return {
        "customer": "cliente",
        "actual": "valor/venta actual",
        "budget": "presupuesto",
        "previous": "valor/venta del periodo anterior",
    }.get(role, role)


def enforce_prompt_contract(
    plan: Dict[str, Any],
    df: pd.DataFrame,
    prompt: str,
    filename: str = "",
    sheet: str = "",
) -> Dict[str, Any]:
    """Make the prompt authoritative and the data the hard boundary.

    - Never accepts self-comparisons.
    - Never allows a requested budget/previous-period metric without the real columns.
    - If the core request is unsupported, returns an explicit insufficient-data dashboard
      instead of silently substituting unrelated KPIs.
    """
    sem = strict_semantic_columns(df)
    intents = requested_intents(prompt)
    missing = _unsupported(intents, sem)

    out = dict(plan or {})
    out["semantic_columns_strict"] = sem
    out["requested_intents"] = intents
    out["missing_requirements"] = missing
    out["contract_guard"] = "r9.1"

    # Remove unsafe/fabricated derived KPIs.
    safe_kpis = []
    for k in out.get("kpis", []) if isinstance(out.get("kpis"), list) else []:
        if not isinstance(k, dict):
            continue
        op = k.get("op")
        label = str(k.get("label") or "")
        if op == "ratio_pct":
            if not k.get("numerator") or not k.get("denominator") or _same_nonempty(k.get("numerator"), k.get("denominator")):
                continue
        elif op == "difference_sum":
            if not k.get("left") or not k.get("right") or _same_nonempty(k.get("left"), k.get("right")):
                continue
        elif op == "variation_pct":
            if not k.get("current") or not k.get("previous") or _same_nonempty(k.get("current"), k.get("previous")):
                continue
        # Never display budget/previous claims when those semantics are absent.
        if _mentions_budget(label) and not sem.get("budget"):
            continue
        if _mentions_previous(label) and not sem.get("previous"):
            continue
        col = str(k.get("column") or "")
        # Avoid numeric identifiers as executive KPIs unless explicitly requested.
        if col and re.search(r"(^|_)(cod|codigo|id)($|_)", _norm(col).replace(" ", "_")) and _norm(col) not in _norm(prompt):
            continue
        safe_kpis.append(k)
    out["kpis"] = safe_kpis[:10]

    # Remove unsafe/fabricated comparison charts.
    safe_charts = []
    for c in out.get("charts", []) if isinstance(out.get("charts"), list) else []:
        if not isinstance(c, dict):
            continue
        title = str(c.get("title") or "")
        if c.get("type") == "comparison_bar":
            ms = [m for m in (c.get("measures") or []) if m]
            if len(ms) < 2 or len(set(ms)) < 2:
                continue
        if _mentions_budget(title) and not sem.get("budget"):
            continue
        if _mentions_previous(title) and not sem.get("previous"):
            continue
        safe_charts.append(c)
    out["charts"] = safe_charts[:8]

    critical = {k: v for k, v in missing.items() if k in {
        "lost_customers", "recovered_customers", "budget", "compliance", "previous_comparison"
    }}
    if critical:
        requested = ", ".join(_intent_label(i) for i in intents if i in critical)
        unique_missing = []
        for vals in critical.values():
            for r in vals:
                if r not in unique_missing:
                    unique_missing.append(r)
        missing_text = ", ".join(_role_label(r) for r in unique_missing)

        out["status"] = "insufficient_data"
        out["title"] = "Dashboard solicitado · Datos insuficientes"
        where = f" · Hoja {sheet}" if sheet else ""
        out["subtitle"] = (
            f"{filename}{where} · No es posible calcular de forma confiable: {requested}. "
            f"Faltan datos reales para: {missing_text}. No se sustituyeron columnas ni se inventaron comparaciones."
        )
        out["kpis"] = []
        out["charts"] = []
        out["filters"] = _safe_filters(df, sem)
        out["table"] = _safe_table(df, sem)
        out["warnings"] = [
            "El prompt se tomó como autoridad.",
            "Los datos reales son el límite del análisis.",
            "No se generaron métricas sustitutas ni comparaciones de una columna contra sí misma.",
            f"Solicitudes no soportadas con esta hoja: {requested}.",
            f"Datos requeridos ausentes: {missing_text}.",
        ]
        out["planner"] = str(out.get("planner") or "unknown") + "|prompt-contract-blocked"
        return out

    out["status"] = "ready"
    out["warnings"] = list(out.get("warnings") or [])
    out["warnings"].append("R9.1 Prompt Contract: plan validado contra columnas reales.")
    out["planner"] = str(out.get("planner") or "unknown") + "|prompt-contract-ok"
    return out
