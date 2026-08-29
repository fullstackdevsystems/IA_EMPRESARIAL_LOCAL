from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, List, Optional


def _norm(v: Any) -> str:
    s = str(v or "").strip().lower()
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    s = re.sub(r"[^a-z0-9_%]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _metric(label, op, **kw):
    d = {"label": label, "op": op}
    d.update(kw)
    return d


def _chart(kind, title, dimension, measure, top_n=10, op="sum"):
    return {"type": kind, "title": title, "dimension": dimension, "measure": measure, "op": op, "top_n": top_n}


def _add_unique(seq: List[Dict[str, Any]], item: Dict[str, Any], key_fields=("label", "title", "column")):
    sig = tuple(item.get(k) for k in key_fields)
    for x in seq:
        if tuple(x.get(k) for k in key_fields) == sig:
            return
    seq.append(item)


def is_enterprise_analytics_prompt(prompt: str) -> bool:
    p = _norm(prompt)
    signals = [
        "dashboard ejecutivo", "kpis ejecutivos", "rentabilidad", "analisis de fletes",
        "utilidad por producto", "clientes mas rentables", "operaciones con utilidad negativa",
        "margen por tonelada", "margen %", "proveedores", "origen destino", "evolucion por fecha",
    ]
    hits = sum(1 for x in signals if _norm(x) in p)
    return hits >= 3 or len(p) > 1800


def _canonical_advanced_df(df, sem: Dict[str, Optional[str]]):
    """Create an in-memory canonical view only for the legacy advanced renderer.

    Source columns are never modified. Canonical aliases let advanced analytics work with
    English or alternate column names while the rest of R10.2 keeps the original columns.
    """
    w = df.copy()
    aliases = {
        "Fecha": "date", "Cod_Cliente": "customer_id", "Cliente": "customer",
        "Articulo": "product", "ctrl_alm": "product_group", "Toneladas_Vendidas": "quantity",
        "Importe_Venta": "revenue", "Costo": "cost", "Utilidad": "profit",
        "Costo_Flete": "freight", "Proveedor": "supplier", "Almacen": "warehouse",
        "Ciudad_Origen": "origin_city", "Ciudad_Destino": "destination_city",
        "Vendedor": "seller", "Refer": "reference",
    }
    for canonical, concept in aliases.items():
        src = sem.get(concept)
        if canonical not in w.columns and src and src in w.columns:
            w[canonical] = w[src]
    return w


def compile_enterprise_prompt(plan: Dict[str, Any], df, prompt: str, filename: str = "", sheet: str = "") -> Dict[str, Any]:
    if not is_enterprise_analytics_prompt(prompt):
        return plan

    from semantic_layer import resolve_semantic_map
    semantic_map = resolve_semantic_map(df)
    sem: Dict[str, Optional[str]] = dict(semantic_map.get("usable") or {})

    out = dict(plan or {})
    kpis: List[Dict[str, Any]] = []
    charts: List[Dict[str, Any]] = []
    filters: List[Dict[str, Any]] = []
    warnings = list(out.get("warnings") or [])

    q, revenue, cost, profit = sem.get("quantity"), sem.get("revenue"), sem.get("cost"), sem.get("profit")
    customer, customer_id = sem.get("customer"), sem.get("customer_id")
    product = sem.get("product_group") or sem.get("product")
    quantity_is_tons = bool(q and ("tonelada" in _norm(q) or "tonnage" in _norm(q) or "tons" in _norm(q)))
    quantity_label = "Toneladas Vendidas" if quantity_is_tons else "Cantidad Vendida"
    per_unit = "Tonelada" if quantity_is_tons else "Unidad"

    if q: _add_unique(kpis, _metric(quantity_label, "sum", column=q, format="number"))
    if revenue: _add_unique(kpis, _metric("Venta Total", "sum", column=revenue, format="currency"))
    if cost: _add_unique(kpis, _metric("Costo Total", "sum", column=cost, format="currency"))
    if profit: _add_unique(kpis, _metric("Utilidad Total", "sum", column=profit, format="currency"))
    if profit and revenue: _add_unique(kpis, _metric("Margen %", "ratio_pct", numerator=profit, denominator=revenue, format="percent"))
    if profit and q: _add_unique(kpis, _metric(f"Utilidad por {per_unit}", "ratio", numerator=profit, denominator=q, format="currency"))
    if cost and q: _add_unique(kpis, _metric(f"Costo por {per_unit}", "ratio", numerator=cost, denominator=q, format="currency"))
    if revenue and q: _add_unique(kpis, _metric(f"Precio Promedio por {per_unit}", "ratio", numerator=revenue, denominator=q, format="currency"))
    if sem.get("product_cost"): _add_unique(kpis, _metric("Costo de Producto", "sum", column=sem["product_cost"], format="currency"))
    if sem.get("freight"): _add_unique(kpis, _metric("Costo de Fletes", "sum", column=sem["freight"], format="currency"))
    if sem.get("other_cost"): _add_unique(kpis, _metric("Otros Costos", "sum", column=sem["other_cost"], format="currency"))
    if sem.get("shrinkage"): _add_unique(kpis, _metric("Merma", "sum", column=sem["shrinkage"], format="number"))
    if customer_id or customer: _add_unique(kpis, _metric("Clientes Únicos", "nunique", column=customer_id or customer, format="integer"))
    if sem.get("reference"): _add_unique(kpis, _metric("Operaciones / Referencias", "nunique", column=sem["reference"], format="integer"))

    filter_specs = [
        ("date", "Fecha"), ("zone", "Zona"), ("category", "Categoría"), ("seller", "Vendedor"),
        ("customer", "Cliente"), ("product", "Producto"), ("product_group", "Producto / Grupo"),
        ("supplier", "Proveedor"), ("warehouse", "Almacén"), ("origin_city", "Ciudad Origen"),
        ("destination_city", "Ciudad Destino"), ("line", "Línea"),
    ]
    seen = set()
    for concept, label in filter_specs:
        col = sem.get(concept)
        if col and col not in seen:
            filters.append({"column": col, "label": label})
            seen.add(col)

    date = sem.get("date")
    seller, zone, category = sem.get("seller"), sem.get("zone"), sem.get("category")
    supplier, warehouse = sem.get("supplier"), sem.get("warehouse")
    origin, destination, freight = sem.get("origin_city"), sem.get("destination_city"), sem.get("freight")
    shrinkage = sem.get("shrinkage")

    if product and q: charts.append(_chart("bar", "Cantidad por Producto / Grupo", product, q, 12))
    if product and profit: charts.append(_chart("bar", "Utilidad por Producto / Grupo", product, profit, 12))
    if date and revenue: charts.append(_chart("line", "Evolución de Venta", date, revenue, 45))
    if customer and profit: charts.append(_chart("bar", "Clientes por Utilidad", customer, profit, 20))
    if customer and revenue: charts.append(_chart("bar", "Top Clientes por Venta", customer, revenue, 20))
    if seller and profit: charts.append(_chart("bar", "Utilidad por Vendedor", seller, profit, 20))
    if zone and profit: charts.append(_chart("bar", "Utilidad por Zona", zone, profit, 20))
    if category and profit: charts.append(_chart("bar", "Utilidad por Categoría", category, profit, 20))
    if supplier and profit: charts.append(_chart("bar", "Utilidad asociada por Proveedor", supplier, profit, 20))
    if supplier and freight: charts.append(_chart("bar", "Costo de Flete por Proveedor", supplier, freight, 20))
    if warehouse and profit: charts.append(_chart("bar", "Utilidad por Almacén", warehouse, profit, 20))
    if origin and freight: charts.append(_chart("bar", "Flete por Ciudad de Origen", origin, freight, 15))
    if destination and freight: charts.append(_chart("bar", "Flete por Ciudad de Destino", destination, freight, 15))
    if shrinkage and product: charts.append(_chart("bar", "Merma por Producto / Grupo", product, shrinkage, 15))

    preferred_concepts = [
        "date", "reference", "customer_id", "customer", "product", "product_group", "quantity",
        "revenue", "cost", "profit", "product_cost", "freight", "other_cost", "shrinkage",
        "seller", "zone", "category", "supplier", "warehouse", "origin_city", "destination_city",
    ]
    table_cols: List[str] = []
    for concept in preferred_concepts:
        c = sem.get(concept)
        if c and c not in table_cols:
            table_cols.append(c)

    out["title"] = "Dashboard Ejecutivo de Ventas y Rentabilidad"
    out["subtitle"] = f"{filename} · Hoja {sheet or 'BD'} · Capa semántica R10.2"
    out["kpis"] = kpis or out.get("kpis", [])
    out["charts"] = charts or out.get("charts", [])
    out["filters"] = filters or out.get("filters", [])
    out["table"] = {"title": "Detalle Operativo", "columns": table_cols, "limit": 250}
    out["top_n"] = 20

    from enterprise_analytics import build_advanced_analytics
    out["advanced"] = build_advanced_analytics(_canonical_advanced_df(df, sem))
    out["semantic_map"] = semantic_map
    out["semantic_columns_strict"] = sem
    ambiguous = [v["label"] for v in semantic_map["concepts"].values() if v.get("confidence") == "AMBIGUOUS"]
    missing_core = [semantic_map["concepts"][k]["label"] for k in ("revenue", "profit", "cost", "quantity") if semantic_map["concepts"].get(k, {}).get("confidence") == "MISSING"]
    if ambiguous:
        warnings.append("R10.2 no autoasignó conceptos ambiguos: " + ", ".join(ambiguous[:8]) + ".")
    if missing_core:
        warnings.append("Conceptos empresariales no detectados con evidencia suficiente: " + ", ".join(missing_core) + ".")

    out["prompt_compiler"] = {
        "version": "r10.2", "mode": "semantic-enterprise-plan", "source_of_truth": sheet or "BD",
        "kpi_count": len(kpis), "chart_count": len(charts), "filter_count": len(filters),
        "advanced_renderer": True, "dynamic_components": True,
        "semantic_policy": semantic_map["policy"],
    }
    out["warnings"] = warnings + [
        "R10.2 resolvió conceptos empresariales por nombre, tipo, contenido y contexto; una coincidencia ambigua nunca se usa para calcular automáticamente.",
        "Los indicadores financieros principales se calculan con código sobre las filas filtradas; el LLM no realiza las sumas base.",
    ]
    from prompt_execution_plan import build_prompt_execution_plan
    out["execution_plan"] = build_prompt_execution_plan(df, prompt, sheet)
    out["planner"] = str(out.get("planner") or "validated") + "|enterprise-prompt-compiler-r10.2|semantic-layer-r10.2"
    return out
