from pathlib import Path
import sys
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"

if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from dashboard_spec_builder import build_dashboard_spec


def check(name, cond):
    if not cond:
        raise AssertionError(name)
    print("PASS", name)


prompt = """
Analiza el archivo desde una perspectiva comercial y de rentabilidad.

Genera un dashboard ejecutivo basado exclusivamente en los datos reales disponibles.

Quiero calcular y mostrar:

- ventas totales
- toneladas vendidas
- costo total
- utilidad
- margen de utilidad %
- precio promedio por tonelada
- costo promedio por tonelada
- utilidad por tonelada
- número de operaciones
- ticket promedio
- clientes activos
- vendedores activos
- productos vendidos

Genera análisis por:

- cliente
- producto
- vendedor
- almacén
- evolución mensual

Quiero las siguientes páginas:

- Resumen Ejecutivo
- Rentabilidad
- Clientes
- Productos
- Vendedores
- Evolución
- Detalle

Todas las métricas derivadas deben indicar su fórmula, dependencias y provenance.

No inventes ninguna métrica.

Si una métrica no puede calcularse con las columnas disponibles o con una regla validada,
muéstrala como N/D o BLOCKED.

No calcules costo total de flete sumando Costo_Flete_Corto,
Costo_Flete_Largo y Costo_Flete_Traspaso salvo que exista una regla empresarial validada que lo autorice.

Si se solicita o aparece una métrica relacionada con flete y no existe dicha regla,
debe quedar BLOCKED.
"""

columns = [
    "cod_Empresa",
    "cod_linea",
    "Cod_Zona",
    "Cod_Cliente",
    "Cliente",
    "Cod_Articulo",
    "Articulo",
    "Refer",
    "Fecha",
    "Zona",
    "Toneladas_Vendidas",
    "Toneladas_Mermadas",
    "Toneladas_Costo",
    "Importe_Venta",
    "Precio_Venta_Dlls",
    "Costo",
    "Costo_Sin_Flete",
    "Costo_Producto",
    "Otros_Costos",
    "Costo_Flete_Corto",
    "Costo_Flete_Largo",
    "Costo_Flete_Traspaso",
    "Cliente_Recoge",
    "Cod_Almacen",
    "Almacen",
    "Ciudad_Origen",
    "Ciudad_Destino",
    "Cod_OrdenCompra",
    "Categoria",
    "ContratoProveedor",
    "Cod_Vendedor",
    "Vendedor",
    "Origen",
    "Tipo_Cambio",
]

# DataFrame mínimo: para esta prueba interesa la estructura semántica,
# no los valores reales del archivo.
df = pd.DataFrame(columns=columns)

spec = build_dashboard_spec(
    df,
    prompt,
    sheet="Datos",
)

pages = spec.get("pages") or []
components = spec.get("components") or []

by_title = {
    str(p.get("title")): p
    for p in pages
}

required_pages = [
    "Resumen Ejecutivo",
    "Rentabilidad",
    "Clientes",
    "Productos",
    "Vendedores",
    "Evolución",
    "Detalle",
]

print("\n=== PÁGINAS GENERADAS ===")
for page in pages:
    print(
        page.get("title"),
        "->",
        len(page.get("components") or []),
        "componentes",
    )

print("\n=== VALIDACIÓN DE PÁGINAS ===")

for page_name in required_pages:
    check(
        f"page_exists:{page_name}",
        page_name in by_title,
    )

for page_name in required_pages:
    page = by_title[page_name]

    check(
        f"page_has_components:{page_name}",
        len(page.get("components") or []) > 0,
    )


page_for_component = {}

for page in pages:
    for cid in page.get("components") or []:
        page_for_component[cid] = page.get("title")


print("\n=== ROUTING DE COMPONENTES ===")

for cid, page_title in sorted(page_for_component.items()):
    print(cid, "->", page_title)


expected_routes = {
    "kpi:profit": "Rentabilidad",
    "kpi:margin_pct": "Rentabilidad",
    "kpi:price_per_unit": "Rentabilidad",
    "kpi:cost_per_unit": "Rentabilidad",
    "kpi:profit_per_unit": "Rentabilidad",
    "kpi:active_customers": "Clientes",
    "kpi:products_sold": "Productos",
    "kpi:active_sellers": "Vendedores",
}

print("\n=== VALIDACIÓN DE ROUTING CLAVE ===")

for cid, expected_page in expected_routes.items():
    check(
        f"route:{cid}->{expected_page}",
        page_for_component.get(cid) == expected_page,
    )


monthly_candidates = [
    cid
    for cid in page_for_component
    if any(
        token in str(cid).lower()
        for token in (
            "monthly",
            "trend",
            "evolution",
            "evolucion",
        )
    )
]

check(
    "evolution_component_exists",
    len(monthly_candidates) > 0,
)

check(
    "evolution_component_routed",
    any(
        page_for_component.get(cid) == "Evolución"
        for cid in monthly_candidates
    ),
)


detail_candidates = [
    c.get("id")
    for c in components
    if (
        c.get("type") == "table"
        or c.get("id") == "analysis:detail"
        or str(c.get("id") or "").startswith("table:")
    )
]

check(
    "detail_component_exists",
    len(detail_candidates) > 0,
)

check(
    "detail_component_routed",
    any(
        page_for_component.get(cid) == "Detalle"
        for cid in detail_candidates
    ),
)


print("\n=== SEGURIDAD DE FLETE ===")

freight_components = [
    c
    for c in components
    if (
        "freight" in str(c.get("id") or "").lower()
        or "flete" in str(c.get("id") or "").lower()
        or "freight" in str(c.get("semantic_role") or "").lower()
        or "flete" in str(c.get("semantic_role") or "").lower()
    )
]

for c in freight_components:
    safe = (
        c.get("status") == "BLOCKED"
        or (
            c.get("status") == "DERIVABLE"
            and (c.get("provenance") or {}).get("source")
            == "capability_rule_registry"
        )
    )

    check(
        f"freight_safe:{c.get('id')}",
        safe,
    )


print("\n=== TRAZABILIDAD R10.13D ===")

for c in components:
    routing = c.get("page_routing")

    check(
        f"routing_trace:{c.get('id')}",
        isinstance(routing, dict)
        and bool(routing.get("assigned_page"))
        and routing.get("planner_version") == "r10.13d"
        and routing.get("status") == "ROUTED",
    )


print("\n=== RESUMEN ===")

for page_name in required_pages:
    page = by_title.get(page_name) or {}
    print(
        f"{page_name}:",
        len(page.get("components") or []),
    )

print(
    "\nPASS R10.13D PAGE COMPOSITION PLANNER"
)