from pathlib import Path
import sys


def check(name, cond):
    if not cond:
        print(f"FAIL {name}")
        raise AssertionError(name)
    print(f"PASS {name}")


if len(sys.argv) < 2:
    raise SystemExit(
        "Uso: python test_r10_13d13_e2e_drill_through_kpi_csv.py <dashboard.html>"
    )

p = Path(sys.argv[1])
t = p.read_text(
    encoding="utf-8",
    errors="replace",
)

print()
print("=== R10.13D.13 E2E DRILL-THROUGH KPI SUMMARY AND CSV EXPORT ===")
print(f"Archivo: {p}")

check("dimension_profitability_present", '"operator":"dimension_profitability"' in t)
check("transaction_table_present", '"operator":"transaction_table"' in t)
check("d12_modal_preserved", "r13bDrillThroughModal" in t)
check("d13_metric_summary", "function drillThroughMetricSummary(" in t)
check("d13_kpi_markup", "r13b-drill-through-kpis" in t)
check("d13_export_button", "data-r13b-drill-through-export" in t)
check("d13_export_function", "function exportDrillThroughCsv()" in t)
check("d13_export_context", "contextualRows.slice()" in t)
check("d13_csv_blob", "new Blob(" in t and "detalle_contextual_" in t)
check("d11_global_filter_preserved", "r13bDrillFilterHost" in t)
check("d11_clear_all_preserved", "data-r13b-clear-all-drills" in t)
check("d10_click_binding_preserved", "node.onclick=applyDrill;" in t)
check("d8_metric_selector_preserved", "data-r13b-dimension-metric" in t)
check("d9_controls_preserved", "data-r13b-dimension-topn" in t and "data-r13b-dimension-view" in t)
check("product_id_preserved", '"product_id":"Cod_Articulo"' in t)
check("seller_id_preserved", '"seller_id":"Cod_Vendedor"' in t)
check("freight_still_blocked", '"id":"kpi:freight"' in t and '"status":"BLOCKED"' in t)
check("coverage_still_93_94", '"percent":93.94' in t or '"coverage_pct":93.94' in t)

print()
print("PASS R10.13D.13 E2E DRILL-THROUGH KPI SUMMARY AND CSV EXPORT")
