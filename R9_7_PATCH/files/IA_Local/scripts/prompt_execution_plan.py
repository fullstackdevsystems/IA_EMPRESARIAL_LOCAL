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


def _has_all(cols: set[str], required: Sequence[str]) -> bool:
    return all(c in cols for c in required)


def _component(key: str, name: str, asked: bool, status: str, detail: str, missing=None, renderer=None) -> Dict[str, Any]:
    return {
        "key": key,
        "name": name,
        "requested": bool(asked),
        "status": status,
        "detail": detail,
        "missing": list(missing or []),
        "renderer": renderer,
    }


def build_prompt_execution_plan(df, prompt: str, sheet: str = "") -> Dict[str, Any]:
    """Compile a prompt into auditable, data-bound execution components.

    R9.7 deliberately does not ask the LLM to calculate metrics. It only turns
    natural-language requirements into a deterministic component plan whose
    readiness is validated against real columns.
    """
    p = _norm(prompt)
    cols = {str(c) for c in df.columns}
    components: List[Dict[str, Any]] = []

    def add(key, name, terms, required=(), detail="", renderer=None, supported=True):
        asked = _asked(p, terms)
        missing = [c for c in required if c not in cols]
        if not asked:
            status = "not_requested"
        elif not supported:
            status = "unsupported"
        elif missing:
            status = "partial" if len(missing) < max(1, len(required)) else "blocked"
        else:
            status = "ready"
        components.append(_component(key, name, asked, status, detail, missing, renderer))

    add("source_validation", "Fuente y validación de BD", ["fuente unica", "hoja bd", "validacion y limpieza", "base de datos principal"], (), "Respeta la hoja seleccionada como fuente del cálculo y registra cobertura.", "validation")
    add("kpis", "KPIs ejecutivos", ["kpis ejecutivos", "toneladas vendidas", "venta total", "utilidad total"], ("Toneladas_Vendidas", "Importe_Venta", "Costo", "Utilidad"), "KPIs ponderados y reactivos.", "kpis")
    add("filters", "Filtros globales", ["filtros globales", "limpiar filtros", "buscar cliente"], (), "Filtros construidos únicamente con columnas existentes.", "filters")
    add("derived_product_reports", "Reportes derivados por producto/grupo", ["reportes derivados", "amarillo", "blanco normal", "blanco pecuario", "sorgo", "rolado", "molido", "cribado", "cualquier producto grupo"], ("ctrl_alm", "Cliente", "Toneladas_Vendidas", "Utilidad"), "Vista dinámica por cualquier valor de ctrl_alm, agrupada por cliente.", "product_views")
    add("pivot_customer", "TD / resumen dinámico por cliente", ["tabla dinamica", "td tabla", "agrupar principalmente por cliente"], ("Cliente", "Toneladas_Vendidas", "Importe_Venta", "Costo", "Utilidad"), "Resumen tipo TD recalculado desde las filas filtradas.", "pivot_customer")
    add("profitability", "Rentabilidad y semáforo", ["rentabilidad", "semaforo", "utilidad por tonelada", "margen %"], ("Importe_Venta", "Costo", "Utilidad", "Toneladas_Vendidas"), "Semáforo basado en signo de utilidad; no inventa meta de margen.", "profitability")
    add("products", "Análisis de productos", ["ventas por producto", "utilidad por producto", "detalle de producto", "ranking producto"], ("ctrl_alm", "Toneladas_Vendidas", "Importe_Venta", "Costo", "Utilidad"), "Ranking y detalle reactivo por producto/grupo.", "products")
    add("customers", "Análisis de clientes", ["clientes mas rentables", "clientes menos rentables", "ranking de clientes", "detalle de cliente"], ("Cod_Cliente", "Cliente", "Toneladas_Vendidas", "Importe_Venta", "Costo", "Utilidad"), "Ranking y drill-down exacto por cliente.", "customers")
    add("sellers", "Ranking de vendedores", ["vendedores", "ranking por vendedor"], ("Vendedor", "Toneladas_Vendidas", "Importe_Venta", "Costo", "Utilidad"), "Tabla reactiva por vendedor.", "rank_seller")
    add("zones", "Análisis por zona", ["zonas", "analisis zona", "ranking por zona"], ("Zona", "Toneladas_Vendidas", "Importe_Venta", "Costo", "Utilidad"), "Tabla reactiva por zona.", "rank_zone")
    add("categories", "Análisis por categoría", ["categorias", "categoria"], ("Categoria", "Toneladas_Vendidas", "Importe_Venta", "Costo", "Utilidad"), "Tabla reactiva por categoría.", "rank_category")
    add("providers", "Análisis de proveedores", ["proveedores", "analisis por proveedor"], ("Proveedor", "Toneladas_Vendidas", "Importe_Venta", "Utilidad"), "Tabla reactiva por proveedor y costos disponibles.", "rank_provider")
    add("warehouses", "Análisis de almacenes", ["almacenes", "analizar almacen"], ("Almacen", "Toneladas_Vendidas", "Importe_Venta", "Utilidad"), "Tabla reactiva por almacén.", "rank_warehouse")
    add("freight", "Análisis de fletes", ["analisis de fletes", "costo total de fletes", "flete por proveedor", "flete por producto"], ("Costo_Flete", "Toneladas_Vendidas"), "Flete total y flete/ton ponderado; rankings por dimensiones disponibles.", "freight")
    add("routes", "Rutas origen → destino", ["origen destino", "rutas", "ciudad origen", "ciudad destino"], ("Ciudad_Origen", "Ciudad_Destino", "Costo_Flete", "Toneladas_Vendidas"), "Rutas reagrupadas con la selección actual.", "routes")
    add("daily", "Evolución diaria", ["evolucion por fecha", "evolucion diaria"], ("Fecha", "Importe_Venta"), "Serie temporal diaria desde Fecha.", "charts")
    add("weekly", "Comparación semanal", ["comparacion por semana", "por semana"], ("Semana", "Importe_Venta"), "Comparación agregada por Semana.", "charts")
    add("shrinkage", "Análisis de mermas", ["mermas", "toneladas mermadas", "merma por producto"], ("Toneladas_Mermadas",), "Merma reactiva y rankings por dimensiones existentes.", "shrinkage")
    add("negative_ops", "Operaciones con pérdida", ["operaciones con perdida", "utilidad negativa"], ("Utilidad",), "Detalle ordenado desde la mayor pérdida.", "negative_ops")
    add("opportunities", "Oportunidades y alertas", ["oportunidades", "alertas", "top oportunidades"], ("Utilidad",), "Hallazgos determinísticos sobre pérdidas, rentabilidad, clientes, productos y fletes.", "opportunities")
    add("detail_table", "Tabla detallada", ["tabla detallada", "detalle completo", "paginar", "ordenar"], (), "Detalle filtrable, ordenable, paginado y exportable a CSV.", "detail_table")
    add("executive_summary", "Resumen ejecutivo", ["resumen ejecutivo", "hallazgos importantes"], (), "Los cálculos se realizan por código; la IA solo puede interpretar resultados ya calculados.", "executive_summary")
    add("math_validation", "Validación matemática", ["validacion cruzada", "validacion matematica", "venta costo contra utilidad", "no mostrar nan"], (), "Auditoría matemática reactiva y controles de divisiones.", "validation")
    add("natural_language", "Preguntas en lenguaje natural", ["preguntas en lenguaje natural", "cual fue el producto", "muestrame las ventas"], (), "Requiere integrar el módulo conversacional con el contexto del dashboard.", None, supported=False)
    add("excel_export", "Exportación Excel desde dashboard", ["exportar a excel", "excel csv", "excel o csv"], (), "CSV filtrado está disponible; exportación XLSX desde el HTML aún no está habilitada.", None, supported=False)

    requested = [c for c in components if c["requested"]]
    ready = [c for c in requested if c["status"] == "ready"]
    partial = [c for c in requested if c["status"] == "partial"]
    blocked = [c for c in requested if c["status"] in {"blocked", "unsupported"}]
    coverage = round((len(ready) + 0.5 * len(partial)) / len(requested) * 100, 1) if requested else 100.0

    return {
        "version": "r9.7",
        "source_of_truth": sheet or "BD",
        "prompt_length": len(str(prompt or "")),
        "requested_count": len(requested),
        "ready_count": len(ready),
        "partial_count": len(partial),
        "blocked_count": len(blocked),
        "coverage_pct": coverage,
        "components": components,
    }
