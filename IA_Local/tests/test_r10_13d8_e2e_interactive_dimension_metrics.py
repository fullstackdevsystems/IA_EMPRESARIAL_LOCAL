from pathlib import Path
import sys

def check(name, cond):
    if not cond:
        print(f"FAIL {name}")
        raise AssertionError(name)
    print(f"PASS {name}")

if len(sys.argv) < 2:
    raise SystemExit(
        "Uso: python test_r10_13d8_e2e_interactive_dimension_metrics.py <dashboard.html>"
    )

p = Path(sys.argv[1])
t = p.read_text(encoding="utf-8", errors="replace")

print()
print("=== R10.13D.8 E2E INTERACTIVE DIMENSION METRICS ===")
print(f"Archivo: {p}")

check("dimension_profitability_present", '"operator":"dimension_profitability"' in t)
check("dimension_bar_chart_present", '"operator":"dimension_bar_chart"' in t)
check("metric_selector_runtime", "data-r13b-dimension-metric" in t)
check("metric_selection_state", "const dimensionMetricSelection={};" in t)
check("metric_selector_event", "select[data-r13b-dimension-metric]" in t)
check("visible_bar_fix_preserved", ".r13b-bar-fill{\n    display:block;" in t)
check("legacy_chart_cleanup_preserved", "LEGACY CHART TOGGLE CLEANUP" in t)
check("product_id_preserved", '"product_id":"Cod_Articulo"' in t)
check("seller_id_preserved", '"seller_id":"Cod_Vendedor"' in t)
check("freight_still_blocked", '"id":"kpi:freight"' in t and '"status":"BLOCKED"' in t)
check("coverage_still_93_94", '"percent":93.94' in t or '"coverage_pct":93.94' in t)

print()
print("PASS R10.13D.8 E2E INTERACTIVE DIMENSION METRICS")
