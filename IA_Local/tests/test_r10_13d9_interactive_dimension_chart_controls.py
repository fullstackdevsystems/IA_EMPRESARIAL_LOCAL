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
print("=== R10.13D.9 INTERACTIVE DIMENSION CHART CONTROLS ===")

check(
    "d8_metric_state_preserved",
    "const dimensionMetricSelection={};" in rt,
)

check(
    "chart_control_state",
    "const dimensionChartControls={};" in rt,
)

check(
    "topn_selector",
    "data-r13b-dimension-topn" in rt
    and "[5,10,15,20,30,50]" in rt,
)

check(
    "sort_order_selector",
    "data-r13b-dimension-order" in rt
    and "Mayor → menor" in rt
    and "Menor → mayor" in rt,
)

check(
    "chart_view_selector",
    "data-r13b-dimension-view" in rt
    and "Barras" in rt
    and "Ranking" in rt,
)

check(
    "state_driven_topn",
    "chartControlState.top_n" in rt
    and "defaultChartTopN" in rt,
)

check(
    "state_driven_sort",
    "chartSortOrder==='asc'" in rt
    and "?a.value-b.value" in rt
    and ":b.value-a.value" in rt,
)

check(
    "state_driven_view",
    "chartView==='list'" in rt
    and "rankingListCard(" in rt
    and ":barsCard(" in rt,
)

check(
    "ranking_list_helper",
    "function rankingListCard(" in rt
    and "r13b-ranking-list" in rt
    and "r13b-ranking-row" in rt,
)

check(
    "control_event_binding",
    "select[data-r13b-dimension-topn]" in rt
    and "select[data-r13b-dimension-order]" in rt
    and "select[data-r13b-dimension-view]" in rt,
)

check(
    "controls_persist_on_rerender",
    "dimensionChartControls[" in rt
    and "renderPages();" in rt,
)

check(
    "d8_metric_selector_preserved",
    "data-r13b-dimension-metric" in rt
    and "selectedChartMetricId" in rt,
)

check(
    "d7_chart_operator_preserved",
    "chartOperator==='dimension_bar_chart'" in rt,
)

check(
    "no_dimension_id_dispatch",
    "id.startsWith('analysis:dimension_')" not in rt,
)

print()
print("PASS R10.13D.9 INTERACTIVE DIMENSION CHART CONTROLS")
