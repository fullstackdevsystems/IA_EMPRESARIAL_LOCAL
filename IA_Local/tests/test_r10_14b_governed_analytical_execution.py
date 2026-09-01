from pathlib import Path
import sys
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from analysis_executor import execute_governed_analytical_plan, EXECUTOR_VERSION
from dashboard_spec_builder import build_dashboard_spec

def check(name, cond):
    if not cond:
        print(f"FAIL {name}")
        raise AssertionError(name)
    print(f"PASS {name}")

print("\n=== R10.14B GOVERNED ANALYTICAL TASK EXECUTION ===")

df = pd.DataFrame({
    "Fecha": ["2026-01-05", "2026-01-20", "2026-02-03"],
    "Cliente": ["A", "A", "B"],
    "Venta": [100.0, 200.0, 300.0],
    "Costo": [70.0, 140.0, 210.0],
})

trend_task = {
    "id": "analysis_plan:trend",
    "analysis": "trend",
    "operator": "time_trend",
    "status": "SUPPORTED",
    "required_dimensions": ["date"],
    "required_metrics": [],
    "evidence": [],
    "optional_evidence": [
        {"kind": "metric", "key": "revenue", "status": "SUPPORTED", "source_columns": ["Venta"]},
        {"kind": "metric", "key": "profit", "status": "DERIVABLE", "source_columns": ["Venta", "Costo"], "rule": {"operator": "difference_of_sums"}},
    ],
}

blocked_task = {
    "id": "analysis_plan:freight_analysis",
    "analysis": "freight_analysis",
    "operator": "freight_analysis",
    "status": "BLOCKED",
    "reason": "Blocked freight evidence.",
    "required_dimensions": [],
    "required_metrics": ["freight"],
    "evidence": [{"kind": "metric", "key": "freight", "status": "BLOCKED", "source_columns": []}],
    "optional_evidence": [],
}

out = execute_governed_analytical_plan(
    df,
    analytical_plan={"tasks": [trend_task, blocked_task]},
    roles={"date": "Fecha", "customer": "Cliente"},
)

check("version", EXECUTOR_VERSION == "r10.14b" and out["schema_version"] == "r10.14b")
check("mode", out["mode"] == "governed-whitelist-execution")
check("two_tasks", out["task_count"] == 2)
check("one_executed", out["executed_count"] == 1)
check("one_not_executed", out["not_executed_count"] == 1)
trend = next(x for x in out["results"] if x["analysis"] == "trend")
check("trend_executed", trend["execution_status"] == "EXECUTED")
check("trend_monthly_rows", [x["period"] for x in trend["result"]["rows"]] == ["2026-01", "2026-02"])
check("trend_revenue", trend["result"]["rows"][0]["revenue"] == 300.0)
check("trend_profit_derived", trend["result"]["rows"][0]["profit"] == 90.0)
freight = next(x for x in out["results"] if x["analysis"] == "freight_analysis")
check("blocked_not_executed", freight["execution_status"] == "NOT_EXECUTED" and freight["result"] is None)
check("governance_blocked_never_executes", out["governance"]["blocked_tasks_are_never_executed"] is True)
check("no_arbitrary_eval", out["governance"]["arbitrary_formula_evaluation"] is False)
check("whitelist_only", out["governance"]["whitelist_only"] is True)
check("builder_integrated", callable(build_dashboard_spec))
print("\nPASS R10.14B GOVERNED ANALYTICAL TASK EXECUTION")
