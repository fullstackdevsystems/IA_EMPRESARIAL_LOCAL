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
print("=== R10.13D.10 CROSS-FILTER DRILL-DOWN ===")

check(
    "drill_state",
    "const dimensionDrillFilters={};" in rt,
)

check(
    "drill_applied_after_base_filters",
    "const baseRows=(" in rt
    and "a.filteredRows()" in rt
    and "activeDrills.every(" in rt,
)

check(
    "drill_uses_identity_column",
    "drill_column:" in rt
    and "identityCol" in rt
    and "drill_value:" in rt
    and "item.identity" in rt,
)

check(
    "display_label_not_filter_grain",
    "drill_value:" in rt
    and "item.identity" in rt
    and "labels:[" in rt
    and "String(label)" in rt,
)

check(
    "bars_clickable",
    "data-r13b-drill-column" in rt
    and "class=\"r13b-bar-row" in rt,
)

check(
    "ranking_clickable",
    "class=\"r13b-ranking-row" in rt
    and "data-r13b-drill-value" in rt,
)

check(
    "click_binding",
    "node.onclick=applyDrill;" in rt,
)

check(
    "keyboard_accessible",
    "node.onkeydown=event=>{" in rt
    and "event.key==='Enter'" in rt
    and "event.key===' '" in rt,
)

check(
    "drill_rerenders_pages",
    "dimensionDrillFilters[" in rt
    and "renderPages();" in rt,
)

check(
    "active_drill_status",
    "Filtro analítico:" in rt
    and "data-r13b-clear-drill" in rt,
)

check(
    "clear_drill",
    "delete dimensionDrillFilters[" in rt,
)

check(
    "d8_metric_selector_preserved",
    "data-r13b-dimension-metric" in rt
    and "dimensionMetricSelection" in rt,
)

check(
    "d9_controls_preserved",
    "data-r13b-dimension-topn" in rt
    and "data-r13b-dimension-order" in rt
    and "data-r13b-dimension-view" in rt,
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
print("PASS R10.13D.10 CROSS-FILTER DRILL-DOWN")
