from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, List, Sequence


def _norm(v: Any) -> str:
    s = str(v or "").strip().lower()
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    s = re.sub(r"[^a-z0-9_%]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _asked(p: str, terms: Sequence[str]) -> bool:
    return any(_norm(t) in p for t in terms)


def _component(key: str, name: str, asked: bool, status: str, detail: str, missing=None, renderer=None) -> Dict[str, Any]:
    return {"key": key, "name": name, "requested": bool(asked), "status": status, "detail": detail, "missing": list(missing or []), "renderer": renderer}


def build_prompt_execution_plan(df, prompt: str, sheet: str = "") -> Dict[str, Any]:
    """R10.2 prompt execution plan validated against semantic business concepts."""
    from semantic_layer import resolve_semantic_map
    smap = resolve_semantic_map(df)
    concepts = smap["concepts"]
    sem = smap["usable"]
    p = _norm(prompt)
    components: List[Dict[str, Any]] = []

    def add(key, name, terms, required_concepts=(), detail="", renderer=None, supported=True):
        asked = _asked(p, terms)
        missing = []
        ambiguous = []
        for concept in required_concepts:
            item = concepts.get(concept, {})
            if item.get("confidence") == "AMBIGUOUS":
                ambiguous.append(item.get("label") or concept)
            elif not sem.get(concept):
                missing.append(item.get("label") or concept)
        if not asked:
            status = "not_requested"
        elif not supported:
            status = "unsupported"
        elif ambiguous:
            status = "blocked"
        elif missing:
            status = "partial" if len(missing) < max(1, len(required_concepts)) else "blocked"
        else:
            status = "ready"
        miss = (["AMBIGUO: " + x for x in ambiguous] + missing)
        components.append(_component(key, name, asked, status, detail, miss, renderer))

    add("source_validation", "Fuente y validación", ["fuente unica", "hoja bd", "validacion y limpieza", "base de datos principal"], (), "Respeta la hoja seleccionada como fuente y registra el mapa semántico.", "validation")
    add("kpis", "KPIs ejecutivos", ["kpis ejecutivos", "toneladas vendidas", "venta total", "utilidad total"], ("quantity", "revenue", "cost", "profit"), "KPIs ponderados y reactivos usando conceptos semánticos validados.", "kpis")
    add("filters", "Filtros globales", ["filtros globales", "limpiar filtros", "buscar cliente"], (), "Filtros construidos únicamente con dimensiones detectadas.", "filters")
    add("derived_product_reports", "Reportes derivados por producto/grupo", ["reportes derivados", "cualquier producto grupo", "producto grupo"], ("product_group", "customer", "quantity", "profit"), "Vista dinámica por grupo/producto y cliente.", "product_views")
    add("pivot_customer", "Resumen dinámico por cliente", ["tabla dinamica", "td tabla", "agrupar principalmente por cliente"], ("customer", "quantity", "revenue", "cost", "profit"), "Resumen tipo TD recalculado desde filas filtradas.", "pivot_customer")
    add("profitability", "Rentabilidad y semáforo", ["rentabilidad", "semaforo", "utilidad por tonelada", "margen %"], ("revenue", "cost", "profit", "quantity"), "Semáforo basado en utilidad y razones ponderadas.", "profitability")
    add("products", "Análisis de productos", ["ventas por producto", "utilidad por producto", "detalle de producto", "ranking producto"], ("product", "quantity", "revenue", "cost", "profit"), "Ranking y detalle reactivo por producto.", "products")
    add("customers", "Análisis de clientes", ["clientes mas rentables", "clientes menos rentables", "ranking de clientes", "detalle de cliente"], ("customer", "quantity", "revenue", "cost", "profit"), "Ranking y drill-down exacto por cliente.", "customers")
    add("sellers", "Ranking de vendedores", ["vendedores", "ranking por vendedor"], ("seller", "quantity", "revenue", "cost", "profit"), "Tabla reactiva por vendedor/ejecutivo/asesor.", "rank_seller")
    add("zones", "Análisis por zona", ["zonas", "analisis zona", "ranking por zona"], ("zone", "quantity", "revenue", "cost", "profit"), "Tabla reactiva por zona/región/territorio.", "rank_zone")
    add("categories", "Análisis por categoría", ["categorias", "categoria"], ("category", "quantity", "revenue", "cost", "profit"), "Tabla reactiva por categoría.", "rank_category")
    add("providers", "Análisis de proveedores", ["proveedores", "analisis por proveedor"], ("supplier", "quantity", "revenue", "profit"), "Tabla reactiva por proveedor.", "rank_provider")
    add("warehouses", "Análisis de almacenes", ["almacenes", "analizar almacen"], ("warehouse", "quantity", "revenue", "profit"), "Tabla reactiva por almacén/bodega.", "rank_warehouse")
    add("freight", "Análisis de fletes", ["analisis de fletes", "costo total de fletes", "flete por proveedor", "flete por producto"], ("freight", "quantity"), "Flete total y flete/unidad; nunca confunde tarifa con costo total.", "freight")
    add("routes", "Rutas origen → destino", ["origen destino", "rutas", "ciudad origen", "ciudad destino"], ("origin_city", "destination_city", "freight", "quantity"), "Rutas reagrupadas con la selección actual.", "routes")
    add("daily", "Evolución diaria", ["evolucion por fecha", "evolucion diaria"], ("date", "revenue"), "Serie temporal desde la fecha transaccional detectada.", "charts")
    add("weekly", "Comparación semanal", ["comparacion por semana", "por semana"], ("week", "revenue"), "Comparación agregada por semana si existe.", "charts")
    add("shrinkage", "Análisis de mermas", ["mermas", "toneladas mermadas", "merma por producto"], ("shrinkage",), "Merma reactiva.", "shrinkage")
    add("negative_ops", "Operaciones con pérdida", ["operaciones con perdida", "utilidad negativa"], ("profit",), "Detalle de operaciones con valor de utilidad negativo.", "negative_ops")
    add("opportunities", "Oportunidades y alertas", ["oportunidades", "alertas", "top oportunidades"], ("profit",), "Hallazgos determinísticos basados en conceptos detectados.", "opportunities")
    add("detail_table", "Tabla detallada", ["tabla detallada", "detalle completo", "paginar", "ordenar"], (), "Detalle filtrable, ordenable y exportable.", "detail_table")
    add("executive_summary", "Resumen ejecutivo", ["resumen ejecutivo", "hallazgos importantes"], (), "La IA solo interpreta resultados previamente calculados.", "executive_summary")
    add("math_validation", "Validación matemática", ["validacion cruzada", "validacion matematica", "venta costo contra utilidad", "no mostrar nan"], (), "Auditoría matemática y del mapa semántico.", "validation")
    add("natural_language", "Preguntas en lenguaje natural", ["preguntas en lenguaje natural", "cual fue el producto", "muestrame las ventas"], (), "Consulta determinística sobre las filas filtradas.", "natural_language")
    add("excel_export", "Exportación Excel", ["exportar a excel", "excel csv", "excel o csv"], (), "XLSX real y CSV de la selección filtrada.", "excel_export")

    requested = [c for c in components if c["requested"]]
    ready = [c for c in requested if c["status"] == "ready"]
    partial = [c for c in requested if c["status"] == "partial"]
    blocked = [c for c in requested if c["status"] in {"blocked", "unsupported"}]
    coverage = round((len(ready) + 0.5 * len(partial)) / len(requested) * 100, 1) if requested else 100.0
    return {
        "version": "r10.2", "source_of_truth": sheet or "BD", "prompt_length": len(str(prompt or "")),
        "requested_count": len(requested), "ready_count": len(ready), "partial_count": len(partial),
        "blocked_count": len(blocked), "coverage_pct": coverage, "components": components,
        "semantic_policy": smap["policy"],
    }
