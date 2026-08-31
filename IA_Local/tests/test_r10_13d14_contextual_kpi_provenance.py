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
print("=== R10.13D.14 CONTEXTUAL KPI PROVENANCE INSPECTOR ===")

check(
    "d13_summary_preserved",
    "function drillThroughMetricSummary(" in rt
    and "data-r13b-drill-through-export" in rt,
)

check(
    "component_metadata_used",
    "const component=" in rt
    and "metric.component" in rt,
)

check(
    "formula_metadata",
    "component.formula" in rt
    and "metric.formula" in rt,
)

check(
    "dependencies_metadata",
    "component.dependencies" in rt
    and "execution.dependency_roles" in rt
    and "metric.dependencies.join(', ')" in rt,
)

check(
    "source_columns_metadata",
    "component.source_columns" in rt
    and "metric.source_columns.join(', ')" in rt,
)

check(
    "provenance_metadata",
    "component.provenance" in rt
    and "provenance.source" in rt
    and "provenance.confidence" in rt,
)

check(
    "rule_metadata",
    "rule.rule_id" in rt
    and "rule.ruleset_version" in rt,
)

check(
    "operator_metadata",
    "execution.operator" in rt
    and "rule.operator" in rt,
)

check(
    "visible_inspector",
    "Fórmula y provenance" in rt
    and "<details>" in rt
    and "<summary>" in rt,
)

check(
    "ruleset_fallback",
    "model.ruleset_version" in rt,
)

check(
    "d13_csv_preserved",
    "function exportDrillThroughCsv()" in rt
    and "drillThroughCurrentRows" in rt,
)

check(
    "d12_context_preserved",
    "rows().filter(" in rt
    and "r13bDrillThroughModal" in rt,
)

check(
    "d11_multifilter_preserved",
    "function renderDrillFilterBar()" in rt
    and "data-r13b-clear-all-drills" in rt,
)

check(
    "d8_d9_preserved",
    "data-r13b-dimension-metric" in rt
    and "data-r13b-dimension-topn" in rt
    and "data-r13b-dimension-view" in rt,
)

check(
    "no_blocked_metric_in_business_defs",
    "item.component.status!=='BLOCKED'" in rt,
)

print()
print("PASS R10.13D.14 CONTEXTUAL KPI PROVENANCE INSPECTOR")
