from pathlib import Path
import sys


def check(name, cond):
    if not cond:
        print(f"FAIL {name}")
        raise AssertionError(name)
    print(f"PASS {name}")


if len(sys.argv) < 2:
    raise SystemExit(
        "Uso: python test_r10_13d15_e2e_contextual_kpi_audit_json.py <dashboard.html>"
    )

p = Path(sys.argv[1])
t = p.read_text(encoding="utf-8", errors="replace")

print()
print("=== R10.13D.15 E2E CONTEXTUAL KPI AUDIT SNAPSHOT JSON ===")
print(f"Archivo: {p}")

check("dimension_profitability_present", '"operator":"dimension_profitability"' in t)
check("transaction_table_present", '"operator":"transaction_table"' in t)
check("d12_modal_preserved", "r13bDrillThroughModal" in t)
check("d13_csv_preserved", "function exportDrillThroughCsv()" in t)
check("d14_provenance_preserved", "Fórmula y provenance" in t)
check("d15_audit_button", "data-r13b-drill-through-audit" in t)
check("d15_snapshot_function", "function drillThroughAuditSnapshot()" in t)
check("d15_schema", "schema_version:'r10.13d.15'" in t)
check("d15_json_export", "function exportDrillThroughAuditJson()" in t)
check("d15_json_blob", "application/json;charset=utf-8;" in t)
check("d15_record_count", "record_count:" in t and "drillThroughCurrentRows.length" in t)
check("d15_governance", "Array.isArray(model.blocked)" in t and "governance:" in t)
check("d11_global_filter_preserved", "r13bDrillFilterHost" in t)
check("d10_click_binding_preserved", "node.onclick=applyDrill;" in t)
check("d8_metric_selector_preserved", "data-r13b-dimension-metric" in t)
check("d9_controls_preserved", "data-r13b-dimension-topn" in t and "data-r13b-dimension-view" in t)
check("product_id_preserved", '"product_id":"Cod_Articulo"' in t)
check("seller_id_preserved", '"seller_id":"Cod_Vendedor"' in t)
check("freight_still_blocked", '"id":"kpi:freight"' in t and '"status":"BLOCKED"' in t)
check("coverage_still_93_94", '"percent":93.94' in t or '"coverage_pct":93.94' in t)
check("profit_rule_present", "universal.profit.revenue_minus_cost.v1" in t)
check("margin_rule_present", "universal.margin_pct.revenue_cost_over_revenue.v1" in t)

print()
print("PASS R10.13D.15 E2E CONTEXTUAL KPI AUDIT SNAPSHOT JSON")
