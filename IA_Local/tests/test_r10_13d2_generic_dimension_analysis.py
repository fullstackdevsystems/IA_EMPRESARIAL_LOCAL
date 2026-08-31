from pathlib import Path
import sys
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from dashboard_spec_builder import build_dashboard_spec
from dynamic_renderer import runtime_markup

def check(name, cond):
    if not cond:
        print(f"FAIL {name}")
        raise AssertionError(name)
    print(f"PASS {name}")

df = pd.DataFrame({
    "Fecha": ["2026-01-01","2026-01-02","2026-01-03"],
    "Cliente": ["Cliente A","Cliente B","Cliente A"],
    "Cod_Cliente": ["A","B","A"],
    "Articulo": ["Producto 1","Producto 2","Producto 1"],
    "Cod_Articulo": ["P1","P2","P1"],
    "Vendedor": ["Vendedor 1","Vendedor 2","Vendedor 1"],
    "Cod_Vendedor": ["V1","V2","V1"],
    "Almacen": ["Almacén 1","Almacén 2","Almacén 1"],
    "Refer": ["R1","R2","R3"],
    "Toneladas_Vendidas": [10.0,20.0,30.0],
    "Importe_Venta": [1000.0,2000.0,3000.0],
    "Costo": [800.0,1600.0,2500.0],
})

prompt = """
Analiza ventas y rentabilidad por cliente, producto, vendedor y almacén.
Calcula ventas totales, toneladas vendidas, costo total, utilidad,
margen de utilidad %, precio promedio por tonelada, costo promedio
por tonelada, utilidad por tonelada, número de operaciones y ticket promedio.
Quiero páginas Resumen Ejecutivo, Clientes, Productos, Vendedores y Detalle.
No inventes métricas.
"""

roles = {
    "date":"Fecha",
    "customer":"Cliente",
    "customer_id":"Cod_Cliente",
    "product":"Articulo",
    "product_id":"Cod_Articulo",
    "seller":"Vendedor",
    "seller_id":"Cod_Vendedor",
    "warehouse":"Almacen",
    "transaction_id":"Refer",
    "quantity":"Toneladas_Vendidas",
    "revenue":"Importe_Venta",
    "cost":"Costo",
}

spec = build_dashboard_spec(
    df,
    prompt,
    sheet="Datos",
    semantic_roles=roles,
)

components = {
    c["id"]:c
    for c in spec.get("components") or []
}

expected = {
    "analysis:dimension_customer",
    "analysis:dimension_product",
    "analysis:dimension_seller",
    "analysis:dimension_warehouse",
}

print()
print("=== R10.13D.2 COMPATIBILITY ON D.7 ===")

for cid in sorted(expected):
    c = components.get(cid)
    check(f"exists:{cid}", c is not None)
    check(f"internal:{cid}", c.get("requested_by_prompt") is False)
    check(
        f"operator:{cid}",
        c.get("execution",{}).get("operator")
        == "dimension_profitability",
    )
    check(
        f"provenance:{cid}",
        c.get("provenance",{}).get("source")
        == "canonical_dimension_profitability_planner",
    )
    check(
        f"revenue_metric:{cid}",
        "kpi:revenue"
        in c.get("execution",{}).get("measure_kpis",[]),
    )

check(
    "customer_identity_role",
    components["analysis:dimension_customer"]["execution"]["identity_role"]
    == "customer_id",
)
check(
    "product_identity_role",
    components["analysis:dimension_product"]["execution"]["identity_role"]
    == "product_id",
)
check(
    "seller_identity_role",
    components["analysis:dimension_seller"]["execution"]["identity_role"]
    == "seller_id",
)
check(
    "warehouse_identity_fallback",
    components["analysis:dimension_warehouse"]["execution"]["identity_role"]
    == "warehouse",
)

coverage = spec.get("coverage") or {}
check(
    "coverage_consistency",
    coverage.get("fulfilled")
    == coverage.get("supported",0)+coverage.get("derivable",0),
)

rt = runtime_markup()
check(
    "dimension_profitability_operator",
    "operator==='dimension_profitability'" in rt,
)
check(
    "dimension_profitability_card",
    "function dimensionProfitabilityCard" in rt,
)
check(
    "legacy_operator_compatibility",
    "operator==='group_by_dimension'" in rt,
)
check(
    "no_dimension_id_dispatch",
    "id.startsWith('analysis:dimension_')" not in rt,
)

print()
print("PASS R10.13D.2 COMPATIBILITY ON R10.13D.7")
