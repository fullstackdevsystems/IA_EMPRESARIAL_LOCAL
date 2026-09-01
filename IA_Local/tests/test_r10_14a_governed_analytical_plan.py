from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
from analysis_planner import build_governed_analytical_plan, PLAN_VERSION
from dashboard_spec_builder import build_dashboard_spec

def check(name, cond):
    if not cond:
        print(f"FAIL {name}")
        raise AssertionError(name)
    print(f"PASS {name}")

print("\n=== R10.14A GOVERNED ANALYTICAL PLAN ===")
components = [
    {"id":"filter:date","status":"SUPPORTED","source_columns":["Fecha"]},
    {"id":"filter:customer","status":"SUPPORTED","source_columns":["Cliente"]},
    {"id":"kpi:revenue","status":"SUPPORTED","source_columns":["Venta"]},
    {"id":"kpi:profit","status":"DERIVABLE","source_columns":["Venta","Costo"],"formula":"revenue - cost","dependencies":["revenue","cost"],"rule":{"rule_id":"universal.profit.revenue_minus_cost.v1"}},
    {"id":"kpi:freight","status":"BLOCKED","source_columns":[],"reason":"No direct semantic role or safe deterministic derivation exists for 'freight'."},
    {"id":"analysis:trend","status":"SUPPORTED"},
    {"id":"analysis:lost_customers","status":"SUPPORTED"},
    {"id":"analysis:freight_analysis","status":"BLOCKED","reason":"Missing required semantic roles: freight"},
]
plan = build_governed_analytical_plan(intent={"analyses":["trend","lost_customers","freight_analysis"]},roles={"date":"Fecha","customer":"Cliente","revenue":"Venta"},components=components)
check("version", PLAN_VERSION == "r10.14a" and plan["schema_version"] == "r10.14a")
check("mode", plan["mode"] == "governed-capability-driven")
check("three_tasks", plan["task_count"] == 3)
check("trend_ready", next(x for x in plan["tasks"] if x["analysis"]=="trend")["status"] == "SUPPORTED")
lost = next(x for x in plan["tasks"] if x["analysis"]=="lost_customers")
check("lost_customers_requires_date_customer_revenue", lost["required_dimensions"] == ["customer","date"] and lost["required_metrics"] == ["revenue"])
freight = next(x for x in plan["tasks"] if x["analysis"]=="freight_analysis")
check("freight_blocked", freight["status"] == "BLOCKED")
check("freight_blocked_evidence", any(x["key"]=="freight" for x in freight["blocked_evidence"]))
check("blocked_not_promoted", plan["governance"]["blocked_metrics_are_not_promoted"] is True)
check("no_arbitrary_eval", plan["governance"]["arbitrary_formula_evaluation"] is False)
check("builder_integrated", callable(build_dashboard_spec))
print("\nPASS R10.14A GOVERNED ANALYTICAL PLAN")
