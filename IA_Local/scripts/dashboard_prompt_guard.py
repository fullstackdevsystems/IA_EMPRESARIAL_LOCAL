from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, List, Optional

def _norm(v: Any) -> str:
    s = str(v or "").strip().lower()
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    s = re.sub(r"[^a-z0-9%]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()

ALIASES = {
    "customer": ["cliente", "customer"],
    "customer_id": ["cod cliente", "cod_cliente", "customer id", "customerid"],
    "product": ["articulo", "producto", "product"],
    "seller": ["vendedor", "ejecutivo", "asesor", "seller"],
    "zone": ["zona", "region", "territorio"],
    "category": ["categoria", "category", "familia"],
    "line": ["cod linea", "cod_linea", "linea"],
    "actual": ["toneladas vendidas actual", "toneladas_vendidas_actual", "venta actual", "actual"],
    "budget": ["toneladas vendidas presupuesto", "toneladas_vendidas_presupuesto", "presupuesto", "budget"],
    "previous": [
        "toneladas vendidas anterior",
        "toneladas_vendidas_anterior",
        "venta anterior",
        "ventas anteriores",
        "periodo anterior",
        "anterior",
        "previous"
    ],
    "revenue": ["importe venta", "importe_venta", "venta", "ventas", "revenue"],
    "quantity": ["toneladas vendidas", "toneladas_vendidas", "cantidad", "unidades", "quantity"],
    "profit": ["utilidad", "ganancia", "profit"],
    "cost": ["costo", "coste", "cost"],
    "date": ["fecha", "date"],
}

def _columns_map(df):
    nmap = {_norm(c): str(c) for c in df.columns}
    out = {}
    for role, aliases in ALIASES.items():
        found = None
        for alias in aliases:
            na = _norm(alias)
            if na in nmap:
                found = nmap[na]
                break
        if not found:
            for alias in sorted((_norm(a) for a in aliases), key=len, reverse=True):
                for nc, orig in nmap.items():
                    if alias and alias in nc:
                        found = orig
                        break
                if found:
                    break
        out[role] = found
    return out

def _contains_any(p: str, phrases: List[str]) -> bool:
    return any(_norm(x) in p for x in phrases)

def _previous_comparison_requested(p: str) -> bool:
    positive = [
        "periodo anterior",
        "venta anterior",
        "ventas anteriores",
        "mes anterior",
        "semana anterior",
        "ano anterior",
        "año anterior",
        "comparar contra anterior",
        "comparacion contra anterior",
        "comparar con anterior",
        "vs anterior",
        "versus anterior",
        "comparar actual contra anterior",
        "actual vs anterior",
    ]
    if _contains_any(p, positive):
        return True

    # Avoid false positives from phrases such as "nombres anteriores",
    # "columnas anteriores", "reglas anteriores", "ejemplos anteriores".
    negative_context = [
        "nombres anteriores",
        "columnas anteriores",
        "reglas anteriores",
        "ejemplos anteriores",
        "valores anteriores",
        "secciones anteriores",
        "hojas anteriores",
        "campos anteriores",
        "parrafos anteriores",
    ]
    if _contains_any(p, negative_context):
        return False

    # Conservative fallback: "anterior" alone is not enough.
    return False

def requested_intents(prompt: str) -> List[str]:
    p = _norm(prompt)
    intents = []
    if _contains_any(p, ["clientes perdidos", "cliente perdido", "perdida de clientes"]):
        intents.append("lost_customers")
    if _contains_any(p, ["recuperacion de clientes", "clientes recuperados", "cliente recuperado"]):
        intents.append("recovered_customers")
    if "presupuesto" in p:
        intents.append("budget")
    if _contains_any(p, ["cumplimiento", "cumplimiento presupuesto", "cumplimiento contra presupuesto"]):
        intents.append("compliance")
    if _previous_comparison_requested(p):
        intents.append("previous_comparison")
    if "riesgo" in p or "riesgos" in p:
        intents.append("risks")
    if "oportunidad" in p or "oportunidades" in p:
        intents.append("opportunities")
    return intents

REQ = {
    "lost_customers": ["customer", "actual", "previous"],
    "recovered_customers": ["customer", "actual", "previous"],
    "budget": ["budget"],
    "compliance": ["actual", "budget"],
    "previous_comparison": ["actual", "previous"],
}

def _label_for_role(role: str) -> str:
    return {
        "customer":"cliente",
        "actual":"valor/venta actual",
        "previous":"valor/venta del periodo anterior",
        "budget":"presupuesto",
    }.get(role, role)

def enforce_prompt_contract(plan: Dict[str, Any], df, prompt: str, filename: str = "", sheet: str = "") -> Dict[str, Any]:
    out = dict(plan or {})
    sem = _columns_map(df)
    intents = requested_intents(prompt)

    missing = {}
    for intent in intents:
        reqs = REQ.get(intent, [])
        absent = [r for r in reqs if not sem.get(r)]
        if absent:
            missing[intent] = absent

    # Remove invalid self-comparisons and identifier sums.
    safe_kpis = []
    for k in out.get("kpis", []) or []:
        op = k.get("op")
        vals = []
        if op == "ratio_pct":
            vals = [k.get("numerator"), k.get("denominator")]
        elif op == "difference_sum":
            vals = [k.get("left"), k.get("right")]
        elif op == "variation_pct":
            vals = [k.get("current"), k.get("previous")]
        if len([x for x in vals if x]) >= 2 and len(set(x for x in vals if x)) < len([x for x in vals if x]):
            continue
        col = str(k.get("column") or "")
        lab = _norm(k.get("label") or "")
        if op == "sum" and (col.lower().startswith("cod_") or col.lower().startswith("id") or " codigo " in f" {lab} "):
            continue
        safe_kpis.append(k)
    out["kpis"] = safe_kpis

    safe_charts = []
    for c in out.get("charts", []) or []:
        if c.get("type") == "comparison_bar":
            ms = [m for m in c.get("measures", []) if m]
            if len(ms) >= 2 and len(set(ms)) < len(ms):
                continue
        safe_charts.append(c)
    out["charts"] = safe_charts

    out["semantic_columns_strict"] = sem
    out["requested_intents"] = intents
    out["missing_requirements"] = missing
    out["contract_guard"] = "r9.3"
    warnings = list(out.get("warnings") or [])
    warnings.extend([
        "El prompt se tomó como autoridad.",
        "Los datos reales son el límite del análisis.",
        "No se generaron métricas sustitutas ni comparaciones de una columna contra sí misma.",
    ])

    if missing:
        human_missing = sorted({_label_for_role(r) for rs in missing.values() for r in rs})
        unsupported = []
        names = {
            "lost_customers":"clientes perdidos",
            "recovered_customers":"recuperación de clientes",
            "budget":"presupuesto",
            "compliance":"cumplimiento contra presupuesto",
            "previous_comparison":"comparación contra periodo anterior",
        }
        for key in missing:
            unsupported.append(names.get(key, key))

        # R9.3 behavior: partial fulfillment.
        # Keep all valid KPIs/charts/table/filter outputs that can be calculated.
        # Only block unsupported requested pieces.
        out["status"] = "partial"
        out["warnings"] = warnings + [
            "No fue posible calcular: " + ", ".join(unsupported) + ".",
            "Datos requeridos ausentes: " + ", ".join(human_missing) + ".",
            "Se generó el mejor dashboard posible únicamente con métricas derivables de los datos reales.",
        ]
        base_sub = out.get("subtitle") or (filename + (f" · Hoja {sheet}" if sheet else ""))
        out["subtitle"] = base_sub + " · Análisis parcial: algunas solicitudes no pudieron calcularse con los datos disponibles."
        out["planner"] = str(out.get("planner") or "validated") + "|prompt-contract-partial"
    else:
        out["status"] = "ready"
        out["warnings"] = warnings
        out["planner"] = str(out.get("planner") or "validated") + "|prompt-contract-ok"

    return out
