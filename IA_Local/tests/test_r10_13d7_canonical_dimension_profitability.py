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
    "Cod_Cliente":["C1","C2","C1","C3"],
    "Cliente":["A","B","A","C"],
    "Cod_Articulo":["P1","P2","P1","P3"],
    "Articulo":["Maíz","Sorgo","Maíz","Melaza"],
    "Cod_Vendedor":["V1","V2","V1","V3"],
    "Vendedor":["Ana","Beto","Ana","Carla"],
    "Almacen":["Norte","Sur","Norte","Centro"],
    "Fecha":pd.to_datetime(
        ["2026-01-01","2026-01-02","2026-02-01","2026-02-02"]
    ),
    "Refer":["R1","R2","R3","R4"],
    "Importe_Venta":[1000.0,2000.0,1500.0,3000.0],
    "Costo":[800.0,1500.0,1200.0,2100.0],
    "Toneladas_Vendidas":[10.0,20.0,15.0,25.0],
})

prompt = """
Analiza ventas y rentabilidad por cliente, producto, vendedor y almacén.
Calcula ventas totales, toneladas vendidas, costo total, utilidad,
margen de utilidad %, precio promedio por tonelada, costo promedio
por tonelada, utilidad por tonelada, número de operaciones y ticket promedio.
Genera páginas Clientes, Productos, Vendedores y Resumen Ejecutivo.
No inventes métricas.
"""

roles = {
    "customer":"Cliente",
    "customer_id":"Cod_Cliente",
    "product":"Articulo",
    "product_id":"Cod_Articulo",
    "seller":"Vendedor",
    "seller_id":"Cod_Vendedor",
    "warehouse":"Almacen",
    "date":"Fecha",
    "transaction_id":"Refer",
    "revenue":"Importe_Venta",
    "cost":"Costo",
    "quantity":"Toneladas_Vendidas",
}

spec = build_dashboard_spec(
    df,
    prompt,
    sheet="Datos",
    semantic_roles=roles,
)

components = {
    c.get("id"):c
    for c in spec.get("components") or []
    if isinstance(c,dict)
}

print()
print("=== R10.13D.7 CANONICAL DIMENSION PROFITABILITY ===")

for role_name in ("customer","product","seller","warehouse"):
    cid = f"analysis:dimension_{role_name}"
    c = components.get(cid)
    check(f"component_exists:{role_name}", c is not None)
    execution = c.get("execution") or {}
    check(
        f"operator:{role_name}",
        execution.get("operator")=="dimension_profitability",
    )
    check(
        f"dimension_role:{role_name}",
        execution.get("dimension_role")==role_name,
    )
    check(
        f"label_role:{role_name}",
        execution.get("label_role")==role_name,
    )
    check(
        f"ten_canonical_kpis:{role_name}",
        len(execution.get("measure_kpis") or [])==10,
    )
    check(
        f"sort_revenue:{role_name}",
        execution.get("sort_metric")=="kpi:revenue",
    )
    check(
        f"top_n:{role_name}",
        execution.get("top_n")==15,
    )

check(
    "customer_identity",
    components["analysis:dimension_customer"]["execution"]["identity_role"]
    =="customer_id",
)
check(
    "product_identity",
    components["analysis:dimension_product"]["execution"]["identity_role"]
    =="product_id",
)
check(
    "seller_identity",
    components["analysis:dimension_seller"]["execution"]["identity_role"]
    =="seller_id",
)
check(
    "warehouse_identity",
    components["analysis:dimension_warehouse"]["execution"]["identity_role"]
    =="warehouse",
)

rt = runtime_markup()
check(
    "operator_driven_dispatch",
    "operator==='dimension_profitability'" in rt,
)
check(
    "no_id_driven_dimension_dispatch",
    "id.startsWith('analysis:dimension_')" not in rt,
)
check(
    "canonical_metric_registry_reused",
    "businessMetricDefinitions()" in rt,
)
check(
    "canonical_metric_executor_reused",
    "aggregateMetric(" in rt,
)
check(
    "identity_grouping",
    "[identityCol]" in rt,
)
check(
    "label_not_part_of_grain",
    "labelCol!==identityCol" in rt,
)
check(
    "blocked_without_metrics",
    "No existen KPIs canónicos soportados" in rt,
)
check(
    "legacy_group_by_dimension_compatible",
    "operator==='group_by_dimension'" in rt,
)

print()
print("PASS R10.13D.7 CANONICAL DIMENSION PROFITABILITY ENGINE")
