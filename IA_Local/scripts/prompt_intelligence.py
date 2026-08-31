from __future__ import annotations
import re, unicodedata
from typing import Any, Dict, Iterable, List, Optional, Set

SCHEMA_VERSION = "r10.13a.3"

def norm(value: Any) -> str:
    s = str(value or "").strip().lower()
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    s = re.sub(r"[^a-z0-9_%]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()

def _contains(text: str, phrases: Iterable[str]) -> bool:
    return any(norm(p) in text for p in phrases)

DOMAIN_LEXICON = {
    "sales": ("ventas","venta","ingresos","comercial","clientes","vendedores","productos","facturas","ticket promedio","toneladas vendidas","sales","revenue"),
    "logistics": ("logistica","flete","fletes","rutas","origen","destino","transporte","embarque","shipping","freight","almacen proveedor","almacen cliente"),
    "receivables": ("cobranza","cartera","cuentas por cobrar","vencido","morosidad","aging","dias vencidos","saldo vencido","receivables","collection"),
    "inventory": ("inventario","stock","existencia","rotacion","obsoleto","obsoletos","stock critico","almacen","inventory","turnover"),
    "finance": ("finanzas","financiero","presupuesto","flujo","ebitda","balance","estado de resultados","cash flow","budget"),
    "purchasing": ("compras","compra","proveedores","orden de compra","abastecimiento","purchasing","procurement"),
    "hr": ("recursos humanos","empleados","personal","nomina","headcount","ausentismo","rotacion de personal","human resources"),
}

METRIC_LEXICON = {
    "revenue": ("ventas","venta total","ingresos","importe venta","revenue","sales"),
    "quantity": ("toneladas","unidades vendidas","cantidad","volumen","quantity","units"),
    "cost": ("costo total","costos","costo","cost"),
    "profit": ("utilidad","ganancia","profit","beneficio"),
    "margin_pct": ("margen","margen %","margen porcentual","porcentaje de margen","margin"),

    "profit_per_unit": (
        "utilidad por tonelada",
        "utilidad promedio por tonelada",
        "utilidad media por tonelada",
        "utilidad por unidad",
        "utilidad promedio por unidad",
        "profit per unit",
        "profit per ton",
        "average profit per unit",
        "average profit per ton",
    ),

    "price_per_unit": (
        "precio por tonelada",
        "precio promedio por tonelada",
        "precio medio por tonelada",
        "precio por unidad",
        "precio promedio por unidad",
        "precio medio por unidad",
        "unit price",
        "average price per unit",
        "average price per ton",
    ),

    "cost_per_unit": (
        "costo por tonelada",
        "costo promedio por tonelada",
        "costo medio por tonelada",
        "costo por unidad",
        "costo promedio por unidad",
        "costo medio por unidad",
        "cost per unit",
        "average cost per unit",
        "average cost per ton",
    ),

    "freight": ("flete","fletes","flete total","costo de fletes","costo flete","freight"),
    "freight_per_unit": ("flete por tonelada","flete por unidad","freight per ton"),
    "operations": ("numero de operaciones","número de operaciones","facturas","operaciones","referencias"),
    "ticket_avg": ("ticket promedio","venta promedio","average ticket"),
    "active_customers": ("clientes activos","active customers"),
    "active_sellers": ("vendedores activos","active sellers"),
    "products_sold": ("productos vendidos","articulos vendidos","artículos vendidos"),
    "stock": ("stock","existencias","inventario actual"),
    "overdue_balance": ("saldo vencido","cartera vencida","overdue balance"),
    "days_overdue": ("dias vencidos","días vencidos","days overdue"),
}

DIMENSION_LEXICON = {
    "date": ("fecha","periodo","período","mes","año","evolucion temporal","evolución temporal"),
    "week": ("semana","semanal","week"),
    "customer": ("cliente","clientes"),
    "product": ("producto","productos","articulo","artículo"),
    "product_group": ("ctrl_alm","grupo de producto","familia de producto","product group"),
    "line": ("linea","línea","lineas","líneas"),
    "seller": ("vendedor","vendedores","ejecutivo","asesor"),
    "zone": ("zona","zonas","region","región"),
    "supplier": ("proveedor","proveedores","supplier"),
    "warehouse": ("almacen","almacén","bodega","warehouse"),
    "origin_city": ("ciudad origen","origen"),
    "destination_city": ("ciudad destino","destino"),
    "invoice": ("factura","facturas","facturacion","facturación","operacion","operación","referencia"),
    "customer_pickup": ("cliente recoge","clientes que recogen","cliente_Recoge","cliente recoge s","pickup customer"),
    "employee": ("empleado","empleados","personal"),
}

ANALYSIS_LEXICON = {
    "executive_summary": ("resumen ejecutivo","principales resultados","conclusiones ejecutivas"),
    "trend": ("evolucion","evolución","tendencia","mensual","por mes","por año","comparacion anual","comparación anual"),
    "ranking": ("ranking","top ","mejores","peores"),
    "customer_profile": ("perfil de cliente","perfil individual","cada cliente"),
    "lost_customers": ("clientes perdidos","dejaron de comprar","inactivos","en riesgo"),
    "profitability": ("rentabilidad","margen","utilidad"),
    "risks": ("riesgos","concentracion","concentración","dependencia","deterioro"),
    "opportunities": ("oportunidades","recuperables","crecimiento"),
    "routes": ("rutas","origen destino","origen → destino"),
    "warehouse_movement": ("movimientos por almacen","movimiento por almacen","almacenes con mayor movimiento","analisis por almacen","análisis por almacén"),
    "origin_share": ("participacion por ciudad origen","participación por ciudad origen","participacion por origen","participación por origen"),
    "destination_share": ("participacion por ciudad destino","participación por ciudad destino","participacion por destino","participación por destino"),
    "monthly_movement": ("evolucion mensual del movimiento","evolución mensual del movimiento","movimiento mensual"),
    "customer_pickup": ("clientes que recogen","cliente recoge","cliente_Recoge"),
    "freight_analysis": ("fletes","flete","flete por tonelada","costo de fletes"),
    "aging": ("aging","antiguedad de saldos","antigüedad de saldos","dias vencidos"),
    "collections": ("cobranza","recuperacion de cartera","recuperación de cartera"),
    "critical_stock": ("stock critico","stock crítico","bajo minimo","bajo mínimo"),
    "inventory_turnover": ("rotacion","rotación","turnover"),
    "obsolete_inventory": ("obsoleto","obsoletos","sin movimiento"),
    "data_quality": ("calidad de datos","duplicados","valores nulos","limitaciones"),
    "detail": ("detalle","tabla detallada","facturas operaciones","facturas / operaciones"),
}

DELIVERABLE_LEXICON = {
    "dashboard": ("dashboard","html interactivo","tablero"),
    "pdf": ("reporte pdf","pdf"),
    "excel": ("excel analitico","excel analítico","xlsx","excel con hojas"),
    "summary": ("resumen ejecutivo","resumen"),
    "detail": ("detalle","tabla detallada"),
}

TABLE_LEXICON = {
    "operations": ("facturas / operaciones","facturas","facturacion","facturación","operaciones"),
    "customers": ("top clientes","clientes"),
    "products": ("top productos","productos"),
    "sellers": ("ranking de vendedores","vendedores"),
    "lost_customers": ("clientes perdidos","clientes inactivos"),
}

PAGE_LEXICON = {
    "summary": ("resumen","resumen ejecutivo"),
    "customers": ("clientes","perfil de cliente"),
    "analysis": ("analisis","análisis","rentabilidad"),
    "operations": ("facturas","facturacion","facturación","operaciones"),
    "customer_profile": ("perfil de cliente","perfil individual"),
    "line_analysis": ("analisis por linea","análisis por línea"),
    "lost_customers": ("clientes perdidos","clientes en riesgo"),
    "logistics": ("logistica","logística","rutas","fletes"),
    "inventory": ("inventario","stock","rotacion","rotación"),
    "receivables": ("cobranza","cartera","aging"),
}

EXPLICIT_PAGE_ALIASES = {
    "resumen": ("summary", "Resumen Ejecutivo"),
    "resumen ejecutivo": ("summary", "Resumen Ejecutivo"),
    "resumen logistico": ("logistics_summary", "Resumen Logístico"),
    "almacenes": ("warehouses", "Almacenes"),
    "rutas": ("routes", "Rutas"),
    "origen y destino": ("origin_destination", "Origen y Destino"),
    "origen destino": ("origin_destination", "Origen y Destino"),
    "evolucion": ("evolution", "Evolución"),
    "detalle logistico": ("logistics_detail", "Detalle Logístico"),
    "calidad de datos": ("data_quality", "Calidad de Datos"),
    "clientes": ("customers", "Clientes"),
    "analisis": ("analysis", "Análisis"),
    "facturas": ("operations", "Facturas / Operaciones"),
    "facturas operaciones": ("operations", "Facturas / Operaciones"),
    "perfil": ("customer_profile", "Perfil de Cliente"),
    "perfil de cliente": ("customer_profile", "Perfil de Cliente"),
    "analisis linea": ("line_analysis", "Análisis por Línea"),
    "analisis por linea": ("line_analysis", "Análisis por Línea"),
    "clientes perdidos": ("lost_customers", "Clientes Perdidos"),
    "inventario": ("inventory", "Inventario"),
    "logistica": ("logistics", "Logística"),
    "cobranza": ("receivables", "Cobranza"),
}

def _page_id_and_title(label: str) -> tuple[str, str]:
    clean = re.sub(r"\s+", " ", str(label or "")).strip(" -•*.:;\t")
    key = norm(clean)
    if key in EXPLICIT_PAGE_ALIASES:
        return EXPLICIT_PAGE_ALIASES[key]
    pid = re.sub(r"[^a-z0-9]+", "_", key).strip("_") or "page"
    return pid, clean or pid.replace("_", " ").title()

def _extract_explicit_pages(raw: str) -> List[Dict[str, str]]:
    lines = str(raw or "").splitlines()
    start = None

    for i, line in enumerate(lines):
        n = norm(line)
        if (
            "siguientes paginas" in n
            or "paginas siguientes" in n
            or "quiero las paginas" in n
        ) and (":" in line or "paginas" in n):
            start = i + 1
            break

    if start is None:
        return []

    out: List[Dict[str, str]] = []

    for line in lines[start:]:
        stripped = line.strip()

        if not stripped:
            if out:
                break
            continue

        m = re.match(r"^[-*•]\s*(.+?)\s*$", stripped)

        if not m:
            if out:
                break
            continue

        label = m.group(1).strip()
        pid, title = _page_id_and_title(label)

        if pid and all(x["id"] != pid for x in out):
            out.append({"id": pid, "title": title})

    return out

def _detect_source_request(raw: str) -> Optional[str]:
    patterns = (
        r"(?im)^\s*(?:fuente\s+principal|hoja\s+principal|hoja\s+fuente)\s*:\s*([A-Za-z0-9_. -]{1,60})\s*$",
        r"(?is)\b(?:usar|usa|utilizar|utiliza)\s+(?:la\s+)?hoja\s+([A-Za-z0-9_. -]{1,60}?)(?=\s*(?:[.,;\r\n]|$))",
    )

    for p in patterns:
        m = re.search(p, raw)

        if m:
            v = re.sub(r"\s+", " ", m.group(1)).strip(" .:-")

            if v:
                return v

    return None

def _detect_domain(text: str) -> Dict[str, Any]:
    scores = {}

    for domain, phrases in DOMAIN_LEXICON.items():
        hits = [p for p in phrases if norm(p) in text]
        scores[domain] = {
            "score": len(hits),
            "hits": hits,
        }

    ranked = sorted(
        scores.items(),
        key=lambda kv: (-kv[1]["score"], kv[0]),
    )

    domain = (
        ranked[0][0]
        if ranked and ranked[0][1]["score"]
        else "generic"
    )

    return {
        "domain": domain,
        "scores": scores,
    }

def _detected_keys(
    text: str,
    lexicon: Dict[str, Iterable[str]],
) -> List[str]:
    return [
        k
        for k, phrases in lexicon.items()
        if _contains(text, phrases)
    ]

NEGATION_CUES = (
    "no generes",
    "no generar",
    "no genere",
    "no incluir",
    "no incluyas",
    "no quiero",
    "sin incluir",
    "excluir",
    "excluye",
    "evita",
    "evitar",
    "no necesito",
    "no se necesitan",
    "no son necesarias",
    "no son necesarios",
)

def _segments(raw: str) -> List[str]:
    parts = re.split(
        r"[\r\n]+|(?<=[.!?;])\s+",
        str(raw or ""),
    )

    return [
        norm(p)
        for p in parts
        if norm(p)
    ]

def _negated_keys(
    raw: str,
    lexicon: Dict[str, Iterable[str]],
) -> List[str]:
    excluded: List[str] = []

    for segment in _segments(raw):
        if not any(cue in segment for cue in NEGATION_CUES):
            continue

        for key, phrases in lexicon.items():
            if key in excluded:
                continue

            if not _contains(segment, phrases):
                continue

            if key == "customer" and (
                "clientes perdidos" in segment
                or "cliente perdido" in segment
                or "perfil de cliente" in segment
            ):
                explicit_customer_exclusion = bool(
                    re.search(
                        r"(?:paginas?\s+de\s+|excluir\s+|sin\s+)"
                        r"(?:los\s+|las\s+)?clientes?"
                        r"(?:\s*[,;]|\s+(?:ni|y)\s+|$)",
                        segment,
                    )
                )

                if not explicit_customer_exclusion:
                    continue

            excluded.append(key)

    return excluded

def _positive_keys(
    raw: str,
    text: str,
    lexicon: Dict[str, Iterable[str]],
) -> tuple[List[str], List[str]]:
    excluded = _negated_keys(raw, lexicon)
    detected = _detected_keys(text, lexicon)

    return (
        [k for k in detected if k not in excluded],
        excluded,
    )

def parse_prompt_intelligence(prompt: str) -> Dict[str, Any]:
    raw = str(prompt or "")
    text = norm(raw)

    domain_info = _detect_domain(text)

    metrics, excluded_metrics = _positive_keys(
        raw,
        text,
        METRIC_LEXICON,
    )

    # "costo total de flete" se refiere al costo de flete,
    # no al KPI genérico de costo.
    if "cost" in metrics and "freight" in metrics:
        cost_segments = [
            seg
            for seg in _segments(raw)
            if _contains(seg, METRIC_LEXICON["cost"])
        ]

        freight_phrases = METRIC_LEXICON["freight"]

        if cost_segments and all(
            _contains(seg, freight_phrases)
            for seg in cost_segments
        ):
            metrics = [
                m
                for m in metrics
                if m != "cost"
            ]

    dimensions, excluded_dimensions = _positive_keys(
        raw,
        text,
        DIMENSION_LEXICON,
    )

    analyses, excluded_analyses = _positive_keys(
        raw,
        text,
        ANALYSIS_LEXICON,
    )

    if (
        domain_info["domain"] == "logistics"
        and "monthly_movement" in analyses
        and "trend" in analyses
    ):
        analyses = [
            a
            for a in analyses
            if a != "trend"
        ]

    deliverables, excluded_deliverables = _positive_keys(
        raw,
        text,
        DELIVERABLE_LEXICON,
    )

    tables, excluded_tables = _positive_keys(
        raw,
        text,
        TABLE_LEXICON,
    )

    pages, excluded_pages = _positive_keys(
        raw,
        text,
        PAGE_LEXICON,
    )

    explicit_pages = _extract_explicit_pages(raw)

    if explicit_pages:
        pages = [
            p["id"]
            for p in explicit_pages
        ]

        excluded_page_set = set(excluded_pages)

        explicit_pages = [
            p
            for p in explicit_pages
            if p["id"] not in excluded_page_set
        ]

        pages = [
            p["id"]
            for p in explicit_pages
        ]

    filters: Set[str] = set()

    if _contains(
        text,
        (
            "filtro",
            "filtrar",
            "filtros globales",
            "fecha inicial",
            "fecha final",
        ),
    ):
        for role in (
            "date",
            "week",
            "customer",
            "product",
            "product_group",
            "line",
            "seller",
            "zone",
            "supplier",
            "warehouse",
        ):
            if role in dimensions:
                filters.add(role)

    if _contains(
        text,
        (
            "fecha inicial",
            "fecha final",
            "desde",
            "hasta",
        ),
    ):
        filters.add("date")

    rankings = []

    if "ranking" in analyses:
        rankings = [
            r
            for r in (
                "customer",
                "product",
                "seller",
                "line",
                "zone",
                "supplier",
            )
            if r in dimensions
        ]

    drilldowns = []

    if _contains(
        text,
        (
            "drill down",
            "drill-down",
            "expansion de registros",
            "expansión de registros",
            "perfil individual",
        ),
    ):
        drilldowns = [
            x
            for x in (
                "customer",
                "product",
                "seller",
                "line",
                "invoice",
            )
            if x in dimensions
        ]

    if not deliverables and raw.strip():
        deliverables = ["summary"]

    requested_items = []

    for kind, items in (
        ("metric", metrics),
        ("dimension", dimensions),
        ("analysis", analyses),
        ("table", tables),
        ("filter", sorted(filters)),
        ("deliverable", deliverables),
    ):
        for item in items:
            requested_items.append(
                {
                    "kind": kind,
                    "key": item,
                }
            )

    return {
        "schema_version": SCHEMA_VERSION,
        "domain": domain_info["domain"],
        "domain_evidence": domain_info["scores"],
        "metrics": metrics,
        "dimensions": dimensions,
        "filters": sorted(filters),
        "tables": tables,
        "rankings": rankings,
        "drilldowns": drilldowns,
        "analyses": analyses,
        "deliverables": deliverables,
        "pages": pages,
        "explicit_pages": explicit_pages,
        "excluded": {
            "metrics": excluded_metrics,
            "dimensions": excluded_dimensions,
            "analyses": excluded_analyses,
            "deliverables": excluded_deliverables,
            "tables": excluded_tables,
            "pages": excluded_pages,
        },
        "requested_source": _detect_source_request(raw),
        "requested_items": requested_items,
        "prompt_length": len(raw),
    }