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
# EXECUCIÓN AGRUPADA AHORA ES OPERATOR-DRIVEN
# ============================================================

check(
    "grouped_business_dispatch",
    "if(operator==='grouped_business_table')" in rt,
)

check(
    "grain_roles_supported",
    "execution.grain_roles" in rt,
)

check(
    "fallback_grain_roles_supported",
    "execution.fallback_grain_roles" in rt,
)

check(
    "label_roles_supported",
    "execution.label_roles" in rt,
)

check(
    "grouped_uses_aggregate_groups",
    "aggregateGroups(" in rt,
)

check(
    "grouped_uses_business_metrics",
    "businessMetricDefinitions()" in rt,
)

check(
    "grouped_uses_canonical_metric_executor",
    "aggregateMetric(" in rt,
)


# ============================================================
# DEDUPLICACIÓN DE GRAIN / LABEL
# ============================================================

check(
    "active_grain_roles",
    "activeGrainRoles" in rt,
)

check(
    "effective_label_roles",
    "effectiveLabelRoles" in rt,
)

check(
    "duplicate_label_protection",
    "!activeGrainRoles.includes(r)" in rt,
)


# ============================================================
# DETALLE DEBE SEGUIR TRANSACCIONAL
# ============================================================

transaction_pos = rt.find(
    "if(operator==='transaction_table')"
)
raw_pos = rt.find(
    "if(operator==='raw_table')"
)

transaction_block = rt[
    transaction_pos:
    raw_pos if raw_pos > transaction_pos else len(rt)
]

check(
    "operations_dispatch_by_operator",
    transaction_pos >= 0,
)

check(
    "operations_resolves_requested_roles",
    "execution.columns" in transaction_block,
)

check(
    "operations_uses_table_card",
    "tableCard(" in transaction_block,
)

check(
    "operations_not_aggregated",
    "aggregateGroups(" not in transaction_block,
)


# ============================================================
# NO DEPENDENCIA DE IDS DE TABLA LEGACY
# ============================================================

check(
    "customers_id_dispatch_removed",
    "id==='table:customers'" not in rt,
)

check(
    "products_id_dispatch_removed",
    "id==='table:products'" not in rt,
)

check(
    "sellers_id_dispatch_removed",
    "id==='table:sellers'" not in rt,
)

check(
    "operations_id_dispatch_removed",
    "id==='table:operations'" not in rt,
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
