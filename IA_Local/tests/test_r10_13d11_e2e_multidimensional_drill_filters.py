from pathlib import Path
import sys

def check(name, cond):
    if not cond:
        print(f"FAIL {name}")
        raise AssertionError(name)
    print(f"PASS {name}")

if len(sys.argv) < 2:
    raise SystemExit(
        "Uso: python test_r10_13d11_e2e_multidimensional_drill_filters.py <dashboard.html>"
    )

p = Path(sys.argv[1])
t = p.read_text(encoding="utf-8", errors="replace")

print()
print("=== R10.13D.11 E2E MULTIDIMENSIONAL DRILL FILTERS ===")
print(f"Archivo: {p}")

check("dimension_profitability_present", '"operator":"dimension_profitability"' in t)
check("d10_drill_state_preserved", "const dimensionDrillFilters={};" in t)
check("d11_global_filter_host", "r13bDrillFilterHost" in t)
check("d11_global_filter_renderer", "function renderDrillFilterBar()" in t)
check("d11_global_filter_chips", "data-r13b-clear-global-drill" in t)
check("d11_clear_all", "data-r13b-clear-all-drills" in t)
check("d11_and_filter_logic", "activeDrills.every(" in t)
check("d10_click_binding_preserved", "node.onclick=applyDrill;" in t)
check("d8_metric_selector_preserved", "data-r13b-dimension-metric" in t)
check("d9_topn_preserved", "data-r13b-dimension-topn" in t)
check("d9_order_preserved", "data-r13b-dimension-order" in t)
check("d9_view_preserved", "data-r13b-dimension-view" in t)
check("product_id_preserved", '"product_id":"Cod_Articulo"' in t)
check("seller_id_preserved", '"seller_id":"Cod_Vendedor"' in t)
check("freight_still_blocked", '"id":"kpi:freight"' in t and '"status":"BLOCKED"' in t)
check("coverage_still_93_94", '"percent":93.94' in t or '"coverage_pct":93.94' in t)

print()
print("PASS R10.13D.11 E2E MULTIDIMENSIONAL DRILL FILTERS")
