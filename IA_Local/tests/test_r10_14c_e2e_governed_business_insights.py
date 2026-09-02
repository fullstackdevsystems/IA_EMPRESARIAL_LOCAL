from pathlib import Path
import sys


def check(name, cond):
    if not cond:
        print(f"FAIL {name}")
        raise AssertionError(name)
    print(f"PASS {name}")


if len(sys.argv) < 2:
    raise SystemExit("Uso: python test_r10_14c_e2e_governed_business_insights.py <dashboard.html>")

p = Path(sys.argv[1])
t = p.read_text(encoding="utf-8", errors="replace")

print("\n=== R10.14C E2E GOVERNED BUSINESS INSIGHTS ===")
print(f"Archivo: {p}")

check("analytical_plan_preserved", '"analytical_plan"' in t and '"schema_version":"r10.14a"' in t)
check("analytical_results_preserved", '"analytical_results"' in t and '"schema_version":"r10.14b"' in t)
check("business_insights_embedded", '"business_insights"' in t)
check("insight_version", '"schema_version":"r10.14c"' in t)
check("insight_mode", '"mode":"deterministic-evidence-only"' in t)
check("llm_numeric_inference_false", '"llm_numeric_inference":false' in t)
check("executed_results_only", '"uses_executed_results_only":true' in t)
check("not_executed_not_promoted", '"not_executed_results_are_never_promoted":true' in t)
check("d18_preserved", "drillThroughVisibleCols" in t and "data-r13b-drill-column" in t)
check("d17_preserved", "drillThroughCompareValues" in t and "data-r13b-drill-sort" in t)
check("d16_preserved", 'id="r13bDrillThroughSearch"' in t and "const drillThroughPageSize=100;" in t)
check("d15_preserved", "function drillThroughAuditSnapshot()" in t)
check("d14_preserved", "Fórmula y provenance" in t)
check("d13_preserved", "function exportDrillThroughCsv()" in t)
check("freight_still_blocked", '"id":"kpi:freight"' in t and '"status":"BLOCKED"' in t)
check("coverage_still_93_94", '"percent":93.94' in t or '"coverage_pct":93.94' in t)
check("profit_rule_present", "universal.profit.revenue_minus_cost.v1" in t)
check("margin_rule_present", "universal.margin_pct.revenue_cost_over_revenue.v1" in t)

print("\nPASS R10.14C E2E GOVERNED BUSINESS INSIGHTS")
