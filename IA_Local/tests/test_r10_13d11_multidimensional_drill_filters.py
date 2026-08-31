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
print("=== R10.13D.11 MULTIDIMENSIONAL DRILL FILTERS ===")

check(
    "d10_drill_state_preserved",
    "const dimensionDrillFilters={};" in rt,
)

check(
    "global_filter_host",
    "r13bDrillFilterHost" in rt
    and "r13b-drill-filter-host" in rt,
)

check(
    "global_filter_renderer",
    "function renderDrillFilterBar()" in rt,
)

check(
    "global_filter_bar",
    "Filtros analíticos" in rt
    and "r13b-drill-filter-bar" in rt,
)

check(
    "global_filter_chips",
    "r13b-drill-chip" in rt
    and "data-r13b-clear-global-drill" in rt,
)

check(
    "active_filter_count",
    "r13b-drill-count" in rt
    and "active.length" in rt,
)

check(
    "clear_individual_global_filter",
    "delete dimensionDrillFilters[" in rt
    and "r13bClearGlobalDrill" in rt,
)

check(
    "clear_all_filters",
    "data-r13b-clear-all-drills" in rt
    and "Object.keys(" in rt
    and "dimensionDrillFilters" in rt,
)

check(
    "multidimensional_and_logic_preserved",
    "activeDrills.every(" in rt,
)

check(
    "same_dimension_replace_other_accumulate",
    "Misma dimensión => reemplaza." in rt
    and "Otra dimensión => se acumula." in rt,
)

check(
    "filter_summary_rerenders",
    "renderDrillFilterBar();" in rt
    and "renderPages();" in rt,
)

check(
    "d10_click_drill_preserved",
    "node.onclick=applyDrill;" in rt
    and "data-r13b-drill-column" in rt,
)

check(
    "d8_metric_selector_preserved",
    "data-r13b-dimension-metric" in rt,
)

check(
    "d9_controls_preserved",
    "data-r13b-dimension-topn" in rt
    and "data-r13b-dimension-order" in rt
    and "data-r13b-dimension-view" in rt,
)

check(
    "no_dimension_id_dispatch",
    "id.startsWith('analysis:dimension_')" not in rt,
)

print()
print("PASS R10.13D.11 MULTIDIMENSIONAL DRILL FILTERS")
