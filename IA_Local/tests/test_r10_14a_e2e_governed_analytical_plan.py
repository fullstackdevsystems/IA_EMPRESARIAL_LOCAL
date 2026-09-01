from pathlib import Path
import sys

def check(name, cond):
    if not cond:
        print(f"FAIL {name}")
        raise AssertionError(name)
    print(f"PASS {name}")

if len(sys.argv) < 2:
    raise SystemExit("Uso: python test_r10_14a_e2e_governed_analytical_plan.py <dashboard.html>")
p = Path(sys.argv[1])
t = p.read_text(encoding="utf-8", errors="replace")
print("\n=== R10.14A E2E GOVERNED ANALYTICAL PLAN ===")
print(f"Archivo: {p}")
check("analytical_plan_embedded", '"analytical_plan"' in t)
check("plan_version", '"schema_version":"r10.14a"' in t)
check("governed_mode", '"mode":"governed-capability-driven"' in t)
check("tasks_present", '"tasks":[' in t)
check("governance_present", '"uses_resolved_capabilities_only":true' in t)
check("no_arbitrary_eval", '"arbitrary_formula_evaluation":false' in t)
check("blocked_not_promoted", '"blocked_metrics_are_not_promoted":true' in t)
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
print("\nPASS R10.14A E2E GOVERNED ANALYTICAL PLAN")
