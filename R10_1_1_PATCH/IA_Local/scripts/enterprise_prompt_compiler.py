from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, List

def _norm(v: Any) -> str:
    s = str(v or "").strip().lower()
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    s = re.sub(r"[^a-z0-9_%]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()

def _has(df, col: str) -> bool:
    return col in df.columns

def _requested(prompt: str, *phrases: str) -> bool:
    p = _norm(prompt)
    return any(_norm(x) in p for x in phrases)

def _metric(label, op, **kw):
    d = {"label": label, "op": op}
    d.update(kw)
    return d

def _chart(kind, title, dimension, measure, top_n=10, op="sum"):
    return {
        "type": kind, "title": title, "dimension": dimension,
        "measure": measure, "op": op, "top_n": top_n
    }

def _add_unique(seq: List[Dict[str, Any]], item: Dict[str, Any], key_fields=("label","title","column")):
    sig = tuple(item.get(k) for k in key_fields)
    for x in seq:
        if tuple(x.get(k) for k in key_fields) == sig:
            return
    seq.append(item)

def is_enterprise_analytics_prompt(prompt: str) -> bool:
    p = _norm(prompt)
    signals = [
        "dashboard ejecutivo", "kpis ejecutivos", "rentabilidad",
        "analisis de fletes", "utilidad por producto", "clientes mas rentables",
        "operaciones con utilidad negativa", "margen por tonelada",
        "margen %", "proveedores", "origen destino", "evolucion por fecha"
    ]
    hits = sum(1 for s in signals if _norm(s) in p)
    return hits >= 3 or len(p) > 1800

def compile_enterprise_prompt(
    plan: Dict[str, Any], df, prompt: str,
    filename: str = "", sheet: str = ""
) -> Dict[str, Any]:
    if not is_enterprise_analytics_prompt(prompt):
        return plan

    out = dict(plan or {})
    kpis: List[Dict[str, Any]] = []
    charts: List[Dict[str, Any]] = []
    filters: List[Dict[str, Any]] = []
    warnings = list(out.get("warnings") or [])

    # KPIs exactos calculados por el renderer sobre las filas filtradas.
    if _has(df, "Toneladas_Vendidas"):
        _add_unique(kpis, _metric("Toneladas Vendidas","sum",column="Toneladas_Vendidas",format="number"))
    if _has(df, "Importe_Venta"):
        _add_unique(kpis, _metric("Venta Total","sum",column="Importe_Venta",format="currency"))
    if _has(df, "Costo"):
        _add_unique(kpis, _metric("Costo Total","sum",column="Costo",format="currency"))
    if _has(df, "Utilidad"):
        _add_unique(kpis, _metric("Utilidad Total","sum",column="Utilidad",format="currency"))
    if _has(df, "Utilidad") and _has(df, "Importe_Venta"):
        _add_unique(kpis, _metric("Margen %","ratio_pct",numerator="Utilidad",denominator="Importe_Venta",format="percent"))
    if _has(df, "Utilidad") and _has(df, "Toneladas_Vendidas"):
        _add_unique(kpis, _metric("Utilidad por Tonelada","ratio",numerator="Utilidad",denominator="Toneladas_Vendidas",format="currency"))
    if _has(df, "Costo") and _has(df, "Toneladas_Vendidas"):
        _add_unique(kpis, _metric("Costo por Tonelada","ratio",numerator="Costo",denominator="Toneladas_Vendidas",format="currency"))
    if _has(df, "Importe_Venta") and _has(df, "Toneladas_Vendidas"):
        _add_unique(kpis, _metric("Precio Promedio por Tonelada","ratio",numerator="Importe_Venta",denominator="Toneladas_Vendidas",format="currency"))
    if _has(df, "Costo_Producto"):
        _add_unique(kpis, _metric("Costo de Producto","sum",column="Costo_Producto",format="currency"))
    if _has(df, "Costo_Flete"):
        _add_unique(kpis, _metric("Costo de Fletes","sum",column="Costo_Flete",format="currency"))
    if _has(df, "Otros_Costos"):
        _add_unique(kpis, _metric("Otros Costos","sum",column="Otros_Costos",format="currency"))
    if _has(df, "Toneladas_Mermadas"):
        _add_unique(kpis, _metric("Toneladas Mermadas","sum",column="Toneladas_Mermadas",format="number"))
    if _has(df, "Cod_Cliente"):
        _add_unique(kpis, _metric("Clientes Únicos","nunique",column="Cod_Cliente",format="integer"))
    if _has(df, "Refer"):
        _add_unique(kpis, _metric("Operaciones / Referencias","nunique",column="Refer",format="integer"))

    # Filtros globales solicitados en el prompt, solo si existen realmente.
    filter_specs = [
        ("Fecha","Fecha"),("Semana","Semana"),("Zona","Zona"),("Categoria","Categoría"),
        ("Vendedor","Vendedor"),("Cliente","Cliente"),("Articulo","Artículo"),
        ("ctrl_alm","Producto / Grupo"),("Proveedor","Proveedor"),("Almacen","Almacén"),
        ("Ciudad_Origen","Ciudad Origen"),("Ciudad_Destino","Ciudad Destino"),
        ("Cliente_Recoge","Cliente Recoge"),("cod_linea","Línea"),
    ]
    for col, label in filter_specs:
        if _has(df, col):
            filters.append({"column": col, "label": label})

    # Gráficas principales derivadas de BD.
    if _has(df,"ctrl_alm") and _has(df,"Toneladas_Vendidas"):
        charts.append(_chart("bar","Toneladas por Producto / Grupo","ctrl_alm","Toneladas_Vendidas",12))
    if _has(df,"ctrl_alm") and _has(df,"Utilidad"):
        charts.append(_chart("bar","Utilidad por Producto / Grupo","ctrl_alm","Utilidad",12))
    if _has(df,"Fecha") and _has(df,"Importe_Venta"):
        charts.append(_chart("line","Evolución Diaria de Venta","Fecha","Importe_Venta",45))
    if _has(df,"Semana") and _has(df,"Importe_Venta"):
        charts.append(_chart("bar","Venta por Semana","Semana","Importe_Venta",20))
    if _has(df,"Cliente") and _has(df,"Utilidad"):
        charts.append(_chart("bar","Clientes por Utilidad","Cliente","Utilidad",20))
    if _has(df,"Cliente") and _has(df,"Importe_Venta"):
        charts.append(_chart("bar","Top Clientes por Venta","Cliente","Importe_Venta",20))
    if _has(df,"Vendedor") and _has(df,"Utilidad"):
        charts.append(_chart("bar","Utilidad por Vendedor","Vendedor","Utilidad",20))
    if _has(df,"Zona") and _has(df,"Utilidad"):
        charts.append(_chart("bar","Utilidad por Zona","Zona","Utilidad",20))
    if _has(df,"Categoria") and _has(df,"Utilidad"):
        charts.append(_chart("bar","Utilidad por Categoría","Categoria","Utilidad",20))
    if _has(df,"Proveedor") and _has(df,"Utilidad"):
        charts.append(_chart("bar","Utilidad asociada por Proveedor","Proveedor","Utilidad",20))
    if _has(df,"Proveedor") and _has(df,"Costo_Flete"):
        charts.append(_chart("bar","Costo de Flete por Proveedor","Proveedor","Costo_Flete",20))
    if _has(df,"Almacen") and _has(df,"Utilidad"):
        charts.append(_chart("bar","Utilidad por Almacén","Almacen","Utilidad",20))
    if _has(df,"Ciudad_Origen") and _has(df,"Costo_Flete"):
        charts.append(_chart("bar","Flete por Ciudad de Origen","Ciudad_Origen","Costo_Flete",15))
    if _has(df,"Ciudad_Destino") and _has(df,"Costo_Flete"):
        charts.append(_chart("bar","Flete por Ciudad de Destino","Ciudad_Destino","Costo_Flete",15))
    if _has(df,"Toneladas_Mermadas") and _has(df,"ctrl_alm"):
        charts.append(_chart("bar","Merma por Producto / Grupo","ctrl_alm","Toneladas_Mermadas",15))

    # Tabla detalle amplia y útil.
    preferred_cols = [
        "Fecha","Semana","Refer","Cod_Cliente","Cliente","Articulo","ctrl_alm",
        "Toneladas_Vendidas","Importe_Venta","Costo","Utilidad",
        "Costo_Producto","Costo_Flete","Otros_Costos","Toneladas_Mermadas",
        "Vendedor","Zona","Categoria","Proveedor","Almacen",
        "Ciudad_Origen","Ciudad_Destino","Cliente_Recoge"
    ]
    table_cols = [c for c in preferred_cols if _has(df,c)]

    out["title"] = "Dashboard Ejecutivo de Ventas y Rentabilidad"
    out["subtitle"] = f"{filename} · Hoja {sheet or 'BD'} · Compilado desde instrucciones del prompt"
    out["kpis"] = kpis or out.get("kpis", [])
    out["charts"] = charts or out.get("charts", [])
    out["filters"] = filters or out.get("filters", [])
    out["table"] = {"title":"Detalle Operativo de BD","columns":table_cols,"limit":250}
    out["top_n"] = 20
    from enterprise_analytics import build_advanced_analytics
    out["advanced"] = build_advanced_analytics(df)
    out["prompt_compiler"] = {
        "version":"r10.1.1",
        "mode":"generic-execution-plan",
        "source_of_truth": sheet or "BD",
        "kpi_count": len(kpis),
        "chart_count": len(charts),
        "filter_count": len(filters),
        "advanced_renderer": True,
        "dynamic_components": True,
    }
    out["warnings"] = warnings + [
        "R10.1.1 compiló un plan de ejecución auditable, métricas, filtros, componentes dinámicos, XLSX real y consulta natural determinística desde el prompt.",
        "Los indicadores financieros principales se calculan con código sobre los datos filtrados; la IA no realiza las sumas base.",
        "Los requisitos no soportados se registran explícitamente en el plan de ejecución sin inventar resultados."
    ]
    from prompt_execution_plan import build_prompt_execution_plan
    out["execution_plan"] = build_prompt_execution_plan(df, prompt, sheet)
    out["planner"] = str(out.get("planner") or "validated") + "|enterprise-prompt-compiler-r10.1.1"
    return out
