from pathlib import Path
import sys

def check(name, cond):
    if not cond:
        print(f"FAIL {name}")
        raise AssertionError(name)
    print(f"PASS {name}")

if len(sys.argv) < 2:
    raise SystemExit(
        "Uso: python test_r10_13d9_e2e_interactive_dimension_chart_controls.py <dashboard.html>"
    )

p = Path(sys.argv[1])
t = p.read_text(encoding="utf-8", errors="replace")

print()
print("=== R10.13D.9 E2E INTERACTIVE DIMENSION CHART CONTROLS ===")
print(f"Archivo: {p}")

check("dimension_profitability_present", '"operator":"dimension_profitability"' in t)
check("dimension_bar_chart_present", '"operator":"dimension_bar_chart"' in t)
check("d8_metric_selector_preserved", "data-r13b-dimension-metric" in t)
check("d9_topn_selector", "data-r13b-dimension-topn" in t)
check("d9_order_selector", "data-r13b-dimension-order" in t)
check("d9_view_selector", "data-r13b-dimension-view" in t)
check("d9_state_present", "const dimensionChartControls={};" in t)
check("ranking_view_present", "function rankingListCard(" in t)
check("visible_bar_fix_preserved", ".r13b-bar-fill{\n    display:block;" in t)
check("legacy_chart_cleanup_preserved", "LEGACY CHART TOGGLE CLEANUP" in t)
check("product_id_preserved", '"product_id":"Cod_Articulo"' in t)
check("seller_id_preserved", '"seller_id":"Cod_Vendedor"' in t)
check("freight_still_blocked", '"id":"kpi:freight"' in t and '"status":"BLOCKED"' in t)
check("coverage_still_93_94", '"percent":93.94' in t or '"coverage_pct":93.94' in t)

print()
print("PASS R10.13D.9 E2E INTERACTIVE DIMENSION CHART CONTROLS")
