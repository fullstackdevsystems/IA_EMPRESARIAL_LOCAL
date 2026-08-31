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
print("=== R10.13D.12 CONTEXTUAL DRILL-THROUGH ===")

check(
    "modal_host",
    "r13bDrillThroughModal" in rt
    and "r13b-drill-through-modal" in rt,
)

check(
    "transaction_columns_from_spec",
    "function drillThroughColumns()" in rt
    and "transaction_table" in rt,
)

check(
    "preserves_current_analytical_context",
    "const contextualRows=" in rt
    and "rows().filter(" in rt,
)

check(
    "exact_identity_filter",
    "row[column]" in rt
    and "String(value)" in rt,
)

check(
    "dimension_table_button",
    "data-r13b-drill-through-column" in rt
    and "Ver detalle" in rt,
)

check(
    "uses_identity_column_and_value",
    'data-r13b-drill-through-column="${esc(identityCol)}"' in rt
    and 'data-r13b-drill-through-value="${esc(item.identity)}"' in rt,
)

check(
    "button_binding",
    "openDrillThrough(" in rt
    and "r13bDrillThroughColumn" in rt,
)

check(
    "active_filters_visible_in_modal",
    "function activeDrillSummary()" in rt
    and "r13b-drill-through-meta" in rt,
)

check(
    "transaction_limit",
    "const limit=500;" in rt,
)

check(
    "close_button",
    "data-r13b-drill-through-close" in rt
    and "closeDrillThrough" in rt,
)

check(
    "escape_close",
    "event.key==='Escape'" in rt,
)

check(
    "d11_multifilter_preserved",
    "function renderDrillFilterBar()" in rt
    and "data-r13b-clear-all-drills" in rt,
)

check(
    "d10_click_filter_preserved",
    "node.onclick=applyDrill;" in rt,
)

check(
    "d8_d9_controls_preserved",
    "data-r13b-dimension-metric" in rt
    and "data-r13b-dimension-topn" in rt
    and "data-r13b-dimension-order" in rt
    and "data-r13b-dimension-view" in rt,
)

check(
    "no_dimension_id_dispatch",
    "id.startsWith('analysis:dimension_')" not in rt,
)

print()
print("PASS R10.13D.12 CONTEXTUAL DRILL-THROUGH")
