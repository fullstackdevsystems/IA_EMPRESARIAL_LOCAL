from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
SCRIPTS=ROOT/'scripts'
if str(SCRIPTS) not in sys.path: sys.path.insert(0,str(SCRIPTS))
from dynamic_renderer import runtime_markup

def check(name,cond):
    if not cond:
        print(f'FAIL {name}')
        raise AssertionError(name)
    print(f'PASS {name}')

rt=runtime_markup()
print('\n=== R10.13D.17 TYPE-AWARE DRILL-THROUGH SORTING ===')
check('d16_search_preserved','function drillThroughFilteredRows()' in rt and 'id="r13bDrillThroughSearch"' in rt)
check('d16_pagination_preserved','const drillThroughPageSize=100;' in rt and 'data-r13b-drill-through-next' in rt)
check('d15_audit_preserved','function drillThroughAuditSnapshot()' in rt)
check('d14_provenance_preserved','Fórmula y provenance' in rt)
check('d13_csv_preserved','function exportDrillThroughCsv()' in rt)
check('sort_state',"let drillThroughSortColumn=null;" in rt and "let drillThroughSortDirection='asc';" in rt)
check('type_aware_compare','function drillThroughCompareValues(' in rt and 'Number.isFinite(an)' in rt)
check('date_compare','datePattern' in rt and 'Date.parse(a)-Date.parse(b)' in rt)
check('locale_compare','localeCompare(' in rt and "'es-MX'" in rt)
check('stable_sort','left.index-right.index' in rt)
check('sortable_headers','data-r13b-drill-sort' in rt and 'r13b-drill-sort' in rt)
check('sort_direction_toggle',"drillThroughSortDirection==='asc'?'desc':'asc'" in rt)
check('new_context_resets_sort','drillThroughSortColumn=null;' in rt)
check('exports_full_context_preserved','of drillThroughCurrentRows' in rt)
print('\nPASS R10.13D.17 TYPE-AWARE DRILL-THROUGH SORTING')
