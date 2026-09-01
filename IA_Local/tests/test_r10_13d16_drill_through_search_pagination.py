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
print("=== R10.13D.16 DRILL-THROUGH SEARCH AND PAGINATION ===")
check("d15_audit_preserved", "function drillThroughAuditSnapshot()" in rt and "Exportar auditoría JSON" in rt)
check("d14_provenance_preserved", "Fórmula y provenance" in rt)
check("d13_csv_preserved", "function exportDrillThroughCsv()" in rt)
check("search_state", "let drillThroughSearch='';" in rt)
check("page_state", "let drillThroughPage=1;" in rt and "const drillThroughPageSize=100;" in rt)
check("filtered_rows_function", "function drillThroughFilteredRows()" in rt)
check("search_across_columns", ".includes(term)" in rt)
check("render_page_function", "function renderDrillThroughTable()" in rt)
check("page_slice", "filtered.slice(start,start+drillThroughPageSize)" in rt)
check("search_input", 'id="r13bDrillThroughSearch"' in rt)
check("pager_buttons", "data-r13b-drill-through-prev" in rt and "data-r13b-drill-through-next" in rt)
check("page_info", 'id="r13bDrillThroughPageInfo"' in rt and "registros visibles de" in rt)
check("controls_binding", "function bindDrillThroughTableControls()" in rt)
check("old_500_limit_removed", "const limit=500;" not in rt and "Mostrando los primeros" not in rt)
check("exports_full_context_preserved", "of drillThroughCurrentRows" in rt)
print()
print("PASS R10.13D.16 DRILL-THROUGH SEARCH AND PAGINATION")
