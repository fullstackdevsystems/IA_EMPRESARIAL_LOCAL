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
print("=== R10.13D.18 DRILL-THROUGH COLUMN VISIBILITY ===")

check("d17_sort_preserved", "drillThroughSortColumn" in rt and "drillThroughCompareValues" in rt)
check("d16_search_preserved", 'id="r13bDrillThroughSearch"' in rt)
check("d16_pagination_preserved", "const drillThroughPageSize=100;" in rt)
check("d15_audit_preserved", "function drillThroughAuditSnapshot()" in rt)
check("d13_csv_preserved", "function exportDrillThroughCsv()" in rt)
check("visible_columns_state", "let drillThroughVisibleCols=[];" in rt)
check("visible_columns_reset", "drillThroughVisibleCols=cols.slice();" in rt)
check("column_picker_ui", "r13b-drill-through-columns" in rt and "data-r13b-drill-column" in rt)
check("render_uses_visible_columns", "drillThroughVisibleCols" in rt)
check("column_change_binding", "checkbox.addEventListener('change'" in rt)
check("at_least_one_column", "if(!drillThroughVisibleCols.length)" in rt)
check("sort_cleared_when_hidden", "!drillThroughVisibleCols.includes(drillThroughSortColumn)" in rt)
check("search_full_context_preserved", "drillThroughCurrentCols" in rt and ".includes(term)" in rt)
check("csv_full_context_preserved", "of drillThroughCurrentRows" in rt and "drillThroughCurrentCols" in rt)
check("audit_full_columns_preserved", "transaction_columns:" in rt and "drillThroughCurrentCols.slice()" in rt)

print()
print("PASS R10.13D.18 DRILL-THROUGH COLUMN VISIBILITY")
