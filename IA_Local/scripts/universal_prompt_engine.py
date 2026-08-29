from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, asdict
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import pandas as pd

VERSION = "r10.2"


def norm(v: Any) -> str:
    s = str(v or "").strip().lower()
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    s = re.sub(r"[^a-z0-9_%]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _tokens(v: Any) -> set[str]:
    return {t for t in norm(v).split() if t}


def _contains_any(text: str, terms: Sequence[str]) -> bool:
    n = norm(text)
    return any(norm(t) in n for t in terms)


def _is_numeric(s: pd.Series) -> bool:
    if pd.api.types.is_numeric_dtype(s):
        return True
    if s.empty:
        return False
    sample = s.dropna().astype(str).head(200)
    if sample.empty:
        return False
    cleaned = sample.str.replace(r"[^0-9,.-]", "", regex=True).str.replace(",", ".", regex=False)
    return pd.to_numeric(cleaned, errors="coerce").notna().mean() >= 0.85


def _is_date(s: pd.Series) -> bool:
    if pd.api.types.is_datetime64_any_dtype(s):
        return True
    sample = s.dropna().head(200)
    if sample.empty:
        return False
    parsed = pd.to_datetime(sample, errors="coerce", dayfirst=False)
    return parsed.notna().mean() >= 0.85


ROLE_SYNONYMS: Dict[str, Sequence[str]] = {
    "date": ("fecha", "date", "invoice date", "order date", "fecha factura", "fecha movimiento"),
    "transaction_id": ("factura", "referencia", "refer", "folio", "ticket", "operacion", "operation", "invoice", "order id", "documento"),
    "customer_id": ("cod cliente", "codigo cliente", "customer id", "cliente id", "id cliente"),
    "customer": ("cliente", "customer", "razon social", "cliente nombre"),
    "product_id": ("cod articulo", "codigo articulo", "cod producto", "sku", "stockcode", "product id"),
    "product": ("articulo", "producto", "description", "descripcion", "product name"),
    "line": ("linea", "linea negocio", "business line"),
    "zone": ("zona", "region", "territorio"),
    "seller": ("vendedor", "ejecutivo", "asesor", "salesperson", "seller"),
    "supplier": ("proveedor", "supplier", "vendor"),
    "warehouse": ("almacen", "warehouse", "bodega"),
    "origin": ("origen", "ciudad origen", "origin", "origin city"),
    "destination": ("destino", "ciudad destino", "destination", "destination city"),
    "category": ("categoria", "category", "segmento", "segment"),
    "quantity": ("cantidad", "quantity", "unidades", "units", "toneladas", "tons", "volumen", "volume"),
    "revenue": ("venta", "ventas", "importe venta", "sales", "revenue", "ingreso", "ingresos", "amount", "importe"),
    "cost": ("costo", "cost", "costo total", "total cost"),
    "profit": ("utilidad", "ganancia", "profit", "gross profit", "beneficio"),
    "freight": ("flete", "freight", "shipping", "costo flete"),
    "budget": ("presupuesto", "budget", "meta", "target", "objetivo"),
    "previous": ("anterior", "previous", "periodo anterior", "año anterior", "year ago", "prior"),
    "status": ("estatus", "status", "estado"),
    "employee": ("empleado", "employee", "colaborador", "trabajador"),
    "department": ("departamento", "department", "area", "área"),
    "balance": ("saldo", "balance", "cartera", "outstanding"),
    "due_date": ("fecha vencimiento", "due date", "vencimiento"),
    "days_overdue": ("dias vencidos", "días vencidos", "days overdue", "aging days"),
    "stock": ("existencia", "stock", "inventario", "inventory", "on hand"),
}

# Priority prevents generic roles from stealing specialized columns.
ROLE_PRIORITY = [
    "due_date", "days_overdue", "customer_id", "product_id", "transaction_id",
    "date", "customer", "product", "line", "zone", "seller", "supplier", "warehouse",
    "origin", "destination", "category", "employee", "department", "budget", "previous",
    "balance", "stock", "freight", "profit", "cost", "revenue", "quantity", "status",
]


def _header_score(column: str, role: str) -> float:
    nc = norm(column)
    ct = _tokens(column)
    best = 0.0
    for synonym in ROLE_SYNONYMS.get(role, ()): 
        ns = norm(synonym)
        st = _tokens(synonym)
        if nc == ns:
            best = max(best, 1.0)
        elif ns and ns in nc:
            best = max(best, 0.9 if len(ns) >= 5 else 0.75)
        elif st and st.issubset(ct):
            best = max(best, 0.82)
        elif ct and st:
            overlap = len(ct & st) / max(len(st), 1)
            best = max(best, overlap * 0.65)
    # Guard against IDs becoming entities.
    if role in {"customer", "product", "seller", "supplier"} and any(x in nc for x in (" cod ", "codigo", " id")):
        best *= 0.45
    return best


def infer_semantic_roles(df: pd.DataFrame) -> Dict[str, Optional[str]]:
    """Infer business roles from arbitrary column names without requiring a fixed schema."""
    candidates: Dict[str, List[Tuple[float, str]]] = {r: [] for r in ROLE_PRIORITY}
    for c in df.columns:
        s = df[c]
        for role in ROLE_PRIORITY:
            score = _header_score(str(c), role)
            if score <= 0:
                continue
            # Type compatibility nudges, not hard requirements.
            if role in {"quantity", "revenue", "cost", "profit", "freight", "budget", "previous", "balance", "stock", "days_overdue"}:
                score += 0.08 if _is_numeric(s) else -0.20
            elif role in {"date", "due_date"}:
                score += 0.08 if _is_date(s) else -0.15
            candidates[role].append((score, str(c)))

    out: Dict[str, Optional[str]] = {}
    used: set[str] = set()
    for role in ROLE_PRIORITY:
        ranked = sorted(candidates[role], key=lambda x: (-x[0], len(norm(x[1]))))
        chosen = next((c for score, c in ranked if score >= 0.58 and c not in used), None)
        out[role] = chosen
        if chosen:
            used.add(chosen)
    return out


def profile_dataframe(df: pd.DataFrame) -> Dict[str, Any]:
    cols = []
    for c in df.columns:
        s = df[c]
        nonnull = int(s.notna().sum())
        cols.append({
            "name": str(c),
            "dtype": str(s.dtype),
            "nonnull": nonnull,
            "nulls": int(len(df) - nonnull),
            "unique": int(s.nunique(dropna=True)),
            "is_numeric": _is_numeric(s),
            "is_date": _is_date(s),
        })
    return {
        "rows": int(len(df)),
        "columns": int(len(df.columns)),
        "duplicates": int(df.duplicated().sum()) if len(df) else 0,
        "column_profile": cols,
    }


def score_transactional_source(df: pd.DataFrame) -> Dict[str, Any]:
    roles = infer_semantic_roles(df)
    found = {k: v for k, v in roles.items() if v}
    score = 0.0
    # Detail/transaction signals.
    for role, weight in {
        "transaction_id": 5, "date": 5, "customer": 3, "product": 3,
        "quantity": 2, "revenue": 2, "cost": 2, "profit": 2,
        "seller": 1, "supplier": 1, "warehouse": 1,
    }.items():
        if roles.get(role):
            score += weight
    score += min(len(df) / 1000.0, 5.0)
    score += min(len(df.columns) / 20.0, 3.0)
    return {"score": round(score, 3), "roles": roles, "found_roles": found, "rows": int(len(df)), "columns": int(len(df.columns))}


def select_transactional_source(sheets: Dict[str, pd.DataFrame], requested_sheet: str = "") -> Dict[str, Any]:
    """Select the most detailed usable source unless the prompt explicitly fixes a source."""
    if requested_sheet and requested_sheet in sheets:
        info = score_transactional_source(sheets[requested_sheet])
        return {"sheet": requested_sheet, "reason": "explicit_prompt_source", **info}
    ranked = []
    for name, df in sheets.items():
        info = score_transactional_source(df)
        ranked.append((info["score"], info["rows"], info["columns"], name, info))
    if not ranked:
        raise ValueError("El archivo no contiene hojas utilizables.")
    ranked.sort(reverse=True)
    _, _, _, name, info = ranked[0]
    return {"sheet": name, "reason": "highest_transactional_detail", **info}


@dataclass
class PromptIntent:
    outputs: List[str]
    requested_metrics: List[str]
    requested_dimensions: List[str]
    requested_analyses: List[str]
    explicit_source: Optional[str]
    top_n: int
    no_invent: bool = True


METRIC_TERMS: Dict[str, Sequence[str]] = {
    "quantity": ("cantidad", "unidades", "toneladas", "volumen", "quantity", "units"),
    "revenue": ("ventas", "venta total", "ingresos", "revenue", "sales"),
    "cost": ("costos", "costo total", "costo", "cost"),
    "profit": ("utilidad", "ganancia", "profit"),
    "margin_pct": ("margen %", "margen porcentual", "margin %"),
    "profit_per_unit": ("utilidad por tonelada", "utilidad por unidad", "ganancia por unidad", "profit per unit"),
    "ticket_avg": ("ticket promedio", "venta promedio", "average ticket"),
    "freight": ("fletes", "costo de flete", "freight"),
    "balance": ("saldo", "cartera", "balance"),
    "stock": ("inventario", "existencia", "stock"),
}

DIMENSION_TERMS: Dict[str, Sequence[str]] = {
    "customer": ("cliente", "clientes", "customer"),
    "product": ("producto", "productos", "articulo", "artículos", "articulos"),
    "line": ("linea", "línea", "lineas", "líneas"),
    "seller": ("vendedor", "vendedores", "ejecutivo", "asesor"),
    "zone": ("zona", "zonas", "region", "región"),
    "supplier": ("proveedor", "proveedores", "supplier"),
    "warehouse": ("almacen", "almacén", "bodega"),
    "category": ("categoria", "categoría", "segmento"),
    "employee": ("empleado", "empleados", "colaborador"),
    "department": ("departamento", "departamentos", "area", "área"),
    "date": ("fecha", "mes", "mensual", "año", "anual", "evolucion", "evolución", "tendencia"),
}

ANALYSIS_TERMS: Dict[str, Sequence[str]] = {
    "trend": ("evolucion", "evolución", "tendencia", "mensual", "anual", "historico", "histórico"),
    "ranking": ("top", "ranking", "mejores", "peores", "mayores", "menores"),
    "lost_customers": ("clientes perdidos", "dejaron de comprar", "inactivos", "en riesgo"),
    "profitability": ("rentabilidad", "margen", "utilidad"),
    "data_quality": ("calidad de datos", "duplicados", "nulos", "inconsistencias"),
    "detail": ("detalle", "facturas", "operaciones", "movimientos"),
    "opportunities": ("oportunidades", "riesgos", "alertas", "anomalias", "anomalías"),
}


def parse_prompt_intent(prompt: str) -> PromptIntent:
    n = norm(prompt)
    outputs: List[str] = []
    for key, terms in {
        "html": ("html", "dashboard", "tablero"),
        "pdf": ("pdf", "reporte ejecutivo"),
        "excel": ("excel", "xlsx", "libro analitico", "libro analítico"),
    }.items():
        if any(norm(t) in n for t in terms):
            outputs.append(key)
    if not outputs:
        outputs = ["html"]
    # Explicit "solo" controls output surface.
    if re.search(r"\bsolo\s+(?:un\s+|el\s+)?pdf\b", n): outputs = ["pdf"]
    elif re.search(r"\bsolo\s+(?:un\s+|el\s+)?(?:excel|xlsx)\b", n): outputs = ["excel"]
    elif re.search(r"\bsolo\s+(?:un\s+|el\s+)?(?:html|dashboard|tablero)\b", n): outputs = ["html"]

    metrics = [k for k, terms in METRIC_TERMS.items() if any(norm(t) in n for t in terms)]
    dims = [k for k, terms in DIMENSION_TERMS.items() if any(norm(t) in n for t in terms)]
    analyses = [k for k, terms in ANALYSIS_TERMS.items() if any(norm(t) in n for t in terms)]

    # Broad analysis: use discovered data rather than a hard-coded business domain.
    if _contains_any(prompt, ("analiza completamente", "analisis completo", "análisis completo", "dashboard completo", "reporte integral")):
        analyses = list(dict.fromkeys(analyses + ["trend", "ranking", "data_quality", "detail", "opportunities"]))

    top_n = 15
    m = re.search(r"\btop\s*(\d{1,3})\b", n)
    if m:
        top_n = max(3, min(int(m.group(1)), 100))

    explicit_source = None
    # Supports phrases like "la hoja BD es la fuente" / "usar hoja Ventas".
    m = re.search(r"\bhoja\s+([a-z0-9_ .-]{1,60}?)\s+(?:es\s+)?(?:la\s+)?(?:fuente|base de datos principal|unica fuente)", n)
    if m:
        explicit_source = m.group(1).strip()

    return PromptIntent(outputs, metrics, dims, analyses, explicit_source, top_n, True)


def _metric_spec(metric: str, roles: Dict[str, Optional[str]]) -> Dict[str, Any]:
    if metric == "quantity":
        c = roles.get("quantity"); return {"key": metric, "label": "Cantidad / Volumen", "op": "sum", "column": c, "ready": bool(c)}
    if metric == "revenue":
        c = roles.get("revenue"); return {"key": metric, "label": "Ingresos / Ventas", "op": "sum", "column": c, "ready": bool(c), "format": "currency"}
    if metric == "cost":
        c = roles.get("cost"); return {"key": metric, "label": "Costo", "op": "sum", "column": c, "ready": bool(c), "format": "currency"}
    if metric == "profit":
        c = roles.get("profit")
        if c: return {"key": metric, "label": "Utilidad", "op": "sum", "column": c, "ready": True, "format": "currency"}
        r, cost = roles.get("revenue"), roles.get("cost")
        return {"key": metric, "label": "Utilidad", "op": "difference_sum", "left": r, "right": cost, "ready": bool(r and cost), "format": "currency"}
    if metric == "margin_pct":
        profit = roles.get("profit"); revenue = roles.get("revenue"); cost = roles.get("cost")
        return {"key": metric, "label": "Margen %", "op": "ratio_pct", "numerator": profit or [revenue, cost], "denominator": revenue, "ready": bool(revenue and (profit or cost)), "format": "percent"}
    if metric == "profit_per_unit":
        q, p, r, c = roles.get("quantity"), roles.get("profit"), roles.get("revenue"), roles.get("cost")
        return {"key": metric, "label": "Utilidad por Unidad", "op": "ratio", "numerator": p or [r, c], "denominator": q, "ready": bool(q and (p or (r and c))), "format": "currency"}
    if metric == "ticket_avg":
        r, tx = roles.get("revenue"), roles.get("transaction_id")
        return {"key": metric, "label": "Ticket Promedio", "op": "sum_div_nunique", "numerator": r, "denominator": tx, "ready": bool(r and tx), "format": "currency"}
    if metric == "freight":
        c = roles.get("freight"); return {"key": metric, "label": "Flete", "op": "sum", "column": c, "ready": bool(c), "format": "currency"}
    if metric == "balance":
        c = roles.get("balance"); return {"key": metric, "label": "Saldo", "op": "sum", "column": c, "ready": bool(c), "format": "currency"}
    if metric == "stock":
        c = roles.get("stock"); return {"key": metric, "label": "Existencia", "op": "sum", "column": c, "ready": bool(c)}
    return {"key": metric, "label": metric, "op": "unsupported", "ready": False}


def compile_universal_plan(df: pd.DataFrame, prompt: str, filename: str = "", sheet: str = "") -> Dict[str, Any]:
    """Compile arbitrary prompt + arbitrary dataframe into a data-bound execution plan."""
    intent = parse_prompt_intent(prompt)
    roles = infer_semantic_roles(df)
    profile = profile_dataframe(df)

    requested_metrics = intent.requested_metrics[:]
    # For broad prompts, add only metrics supported by discovered roles.
    if _contains_any(prompt, ("analiza completamente", "analisis completo", "análisis completo", "dashboard completo", "reporte integral")):
        discovered_defaults = [m for m in ("quantity", "revenue", "cost", "profit", "margin_pct", "ticket_avg", "balance", "stock") if _metric_spec(m, roles)["ready"]]
        requested_metrics = list(dict.fromkeys(requested_metrics + discovered_defaults))

    metric_specs = [_metric_spec(m, roles) for m in requested_metrics]
    ready_metrics = [m for m in metric_specs if m.get("ready")]
    blocked_metrics = [m for m in metric_specs if not m.get("ready")]

    requested_dims = intent.requested_dimensions[:]
    if not requested_dims:
        requested_dims = [r for r in ("customer", "product", "seller", "zone", "supplier", "warehouse", "category", "employee", "department", "date") if roles.get(r)]
    dimensions = [{"role": d, "column": roles.get(d), "ready": bool(roles.get(d))} for d in requested_dims]

    filters = [{"column": d["column"], "label": d["role"].replace("_", " ").title(), "role": d["role"]} for d in dimensions if d["ready"]]
    charts: List[Dict[str, Any]] = []
    primary_measure = next((m for m in ready_metrics if m.get("op") == "sum" and m.get("column")), None)
    if primary_measure:
        for d in dimensions:
            if d["ready"] and d["role"] != "date":
                charts.append({"type": "bar", "title": f"{primary_measure['label']} por {d['role'].replace('_',' ').title()}", "dimension": d["column"], "measure": primary_measure["column"], "op": "sum", "top_n": intent.top_n})
                if len(charts) >= 4: break
        if roles.get("date"):
            charts.insert(0, {"type": "line", "title": f"Evolución de {primary_measure['label']}", "dimension": roles["date"], "measure": primary_measure["column"], "op": "sum", "top_n": 60})

    status = "ready" if not blocked_metrics else ("partial" if ready_metrics else "blocked")
    warnings = []
    for m in blocked_metrics:
        warnings.append(f"N/D: la métrica '{m['label']}' fue solicitada pero no puede calcularse con las columnas disponibles.")

    return {
        "version": VERSION,
        "mode": "universal-prompt-driven",
        "status": status,
        "title": "Dashboard generado desde el prompt y los datos",
        "subtitle": f"{filename}{' · Hoja '+sheet if sheet else ''}",
        "intent": asdict(intent),
        "semantic_roles": roles,
        "data_profile": profile,
        "kpis": ready_metrics,
        "blocked_metrics": blocked_metrics,
        "filters": filters,
        "charts": charts,
        "table": {"title": "Detalle de datos", "columns": [str(c) for c in df.columns], "limit": 250},
        "top_n": intent.top_n,
        "warnings": warnings,
        "calculation_policy": "deterministic_python",
        "no_invent_data": True,
    }
