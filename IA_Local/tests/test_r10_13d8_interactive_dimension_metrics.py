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
print("=== R10.13D.8 INTERACTIVE DIMENSION METRICS ===")

check(
    "metric_selection_state",
    "const dimensionMetricSelection={};" in rt,
)

check(
    "selected_metric_overrides_default",
    "dimensionMetricSelection[c.id]" in rt
    and "defaultChartMetricId" in rt
    and "selectedChartMetricId" in rt,
)

check(
    "selector_markup",
    'data-r13b-dimension-metric="${esc(c.id)}"' in rt,
)

check(
    "selector_uses_canonical_metric_defs",
    "metricDefs.length>1" in rt
    and "${esc(metric.label)}" in rt,
)

check(
    "selector_preserves_selected_option",
    "metric.id===chartMetricDef.id" in rt,
)

check(
    "selector_event_binding",
    "select[data-r13b-dimension-metric]" in rt
    and "select.onchange=()=>{" in rt,
)

check(
    "selection_persists_across_rerender",
    "dimensionMetricSelection[" in rt
    and "renderPages();" in rt,
)

check(
    "chart_uses_selected_metric",
    "item.metrics[" in rt
    and "chartMetricDef.id" in rt,
)

check(
    "metric_control_css",
    ".r13b-metric-control{" in rt
    and ".r13b-metric-select{" in rt,
)

check(
    "d7_chart_operator_preserved",
    "chartOperator==='dimension_bar_chart'" in rt,
)

check(
    "d7_chart_and_table_preserved",
    "${metricSelectorHtml}" in rt
    and "${chartHtml}" in rt
    and 'class="r13b-table"' in rt,
)

check(
    "operator_driven_dimension_dispatch_preserved",
    "if(operator==='dimension_profitability')" in rt,
)

check(
    "no_dimension_id_dispatch",
    "id.startsWith('analysis:dimension_')" not in rt,
)

print()
print("PASS R10.13D.8 INTERACTIVE DIMENSION METRIC SELECTOR")
