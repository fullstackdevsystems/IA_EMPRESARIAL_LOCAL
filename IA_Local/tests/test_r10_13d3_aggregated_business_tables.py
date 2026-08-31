from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"

if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


from dynamic_renderer import runtime_markup


def check(name, cond):
    if cond:
        print(f"PASS {name}")
    else:
        print(f"FAIL {name}")
        raise AssertionError(name)


rt = runtime_markup()


print()
print("=== R10.13D.3 AGGREGATED BUSINESS TABLES ===")


# ============================================================
# INFRAESTRUCTURA DE AGRUPACIÓN
# ============================================================

check(
    "canonical_kpi_lookup",
    "function canonicalKpi" in rt,
)

check(
    "aggregate_groups_exists",
    "function aggregateGroups" in rt,
)

check(
    "aggregate_metric_exists",
    "function aggregateMetric" in rt,
)

check(
    "aggregated_table_card_exists",
    "function aggregatedTableCard" in rt,
)

check(
    "business_metric_definitions_exists",
    "function businessMetricDefinitions" in rt,
)


# ============================================================
# REUTILIZA AUTORIDAD CANÓNICA R10.13C
# ============================================================

check(
    "canonical_kpi_value_used",
    "return kpiValue(" in rt,
)

check(
    "profit_component_used",
    "kpi:profit" in rt,
)

check(
    "margin_component_used",
    "kpi:margin_pct" in rt,
)

check(
    "operations_component_used",
    "kpi:operations" in rt,
)

check(
    "ticket_avg_component_used",
    "kpi:ticket_avg" in rt,
)

check(
    "price_per_unit_component_used",
    "kpi:price_per_unit" in rt,
)

check(
    "cost_per_unit_component_used",
    "kpi:cost_per_unit" in rt,
)

check(
    "profit_per_unit_component_used",
    "kpi:profit_per_unit" in rt,
)


# ============================================================
# CLIENTES
# ============================================================

check(
    "customers_dispatch",
    "id==='table:customers'" in rt,
)

check(
    "customer_id_role",
    "role('customer_id')" in rt,
)

check(
    "customer_role",
    "role('customer')" in rt,
)

check(
    "customers_aggregated",
    "aggregatedTableCard(\n                'Clientes'" in rt,
)


# ============================================================
# PRODUCTOS
# ============================================================

check(
    "products_dispatch",
    "id==='table:products'" in rt,
)

check(
    "product_id_role",
    "role('product_id')" in rt,
)

check(
    "product_role",
    "role('product')" in rt,
)

check(
    "products_aggregated",
    "aggregatedTableCard(\n                'Productos'" in rt,
)


# ============================================================
# VENDEDORES
# ============================================================

check(
    "sellers_dispatch",
    "id==='table:sellers'" in rt,
)

check(
    "seller_id_role",
    "role('seller_id')" in rt,
)

check(
    "seller_role",
    "role('seller')" in rt,
)

check(
    "sellers_aggregated",
    "aggregatedTableCard(\n                'Vendedores'" in rt,
)


# ============================================================
# DETALLE DEBE SEGUIR TRANSACCIONAL
# ============================================================

check(
    "operations_dispatch",
    "id==='table:operations'" in rt,
)

check(
    "operations_keeps_refer",
    "'Refer'" in rt,
)

check(
    "operations_uses_table_card",
    "tableCard(\n                'Operaciones'" in rt,
)

check(
    "operations_not_aggregated",
    "aggregatedTableCard(\n                'Operaciones'" not in rt,
)


# ============================================================
# AGRUPACIÓN NO DEBE USAR REFER COMO CLAVE DE ENTIDAD
# ============================================================

aggregate_block = rt.split(
    "function aggregateGroups",
    1,
)[1].split(
    "function aggregateMetric",
    1,
)[0]

check(
    "refer_not_in_generic_group_keys",
    "Refer" not in aggregate_block,
)


# ============================================================
# MÉTRICAS ESPERADAS
# ============================================================

for label in [
    "Ventas",
    "Costo",
    "Utilidad",
    "Margen %",
    "Toneladas",
    "Operaciones",
    "Ticket Promedio",
    "Precio / Ton",
    "Costo / Ton",
    "Utilidad / Ton",
]:
    check(
        f"metric_label:{label}",
        label in rt,
    )


# ============================================================
# SEGURIDAD
# ============================================================

check(
    "blocked_metrics_excluded",
    "item.component.status!=='BLOCKED'" in rt,
)

check(
    "no_direct_profit_formula_in_table_executor",
    "item.value+=(" not in rt.split(
        "R10.13D.3",
        1,
    )[-1],
)


print()
print(
    "PASS R10.13D.3 "
    "AGGREGATED BUSINESS TABLE EXECUTOR"
)