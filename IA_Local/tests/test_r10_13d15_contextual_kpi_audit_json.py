from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"

if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from dynamic_renderer import runtime_markup


def check(name, cond):
    if not cond:
        print(f"FAIL {name}")
        raise AssertionError(name)
    print(f"PASS {name}")


rt = runtime_markup()

print()
print("=== R10.13D.15 CONTEXTUAL KPI AUDIT SNAPSHOT JSON ===")

check("d14_provenance_preserved", "Fórmula y provenance" in rt and "rule.rule_id" in rt)
check("audit_button", "data-r13b-drill-through-audit" in rt and "Exportar auditoría JSON" in rt)
check("audit_context_state", "drillThroughCurrentContext" in rt)
check("snapshot_function", "function drillThroughAuditSnapshot()" in rt)
check("snapshot_schema", "schema_version:'r10.13d.15'" in rt and "contextual_kpi_audit_snapshot" in rt)
check("exact_context_record_count", "record_count:" in rt and "drillThroughCurrentRows.length" in rt)
check("snapshot_uses_metric_summary", "drillThroughMetricSummary(" in rt and "metrics:" in rt)
check("snapshot_formula_dependencies", "formula:metric.formula" in rt and "metric.dependencies.slice()" in rt)
check("snapshot_provenance_rule", "metric.provenance_source" in rt and "metric.rule_id" in rt and "metric.ruleset_version" in rt)
check("blocked_governance", "Array.isArray(model.blocked)" in rt and "governance:" in rt)
check("json_export", "function exportDrillThroughAuditJson()" in rt and "JSON.stringify(" in rt and "application/json;charset=utf-8;" in rt)
check("json_filename", "auditoria_contextual_" in rt and "+'.json'" in rt)
check("audit_binding", "'[data-r13b-drill-through-audit]'" in rt and "exportDrillThroughAuditJson" in rt)
check("d13_csv_preserved", "function exportDrillThroughCsv()" in rt and "data-r13b-drill-through-export" in rt)
check("d12_context_preserved", "rows().filter(" in rt and "r13bDrillThroughModal" in rt)
check("no_raw_rows_embedded_in_audit", "rows:drillThroughCurrentRows" not in rt and "raw_rows" not in rt)

print()
print("PASS R10.13D.15 CONTEXTUAL KPI AUDIT SNAPSHOT JSON")
