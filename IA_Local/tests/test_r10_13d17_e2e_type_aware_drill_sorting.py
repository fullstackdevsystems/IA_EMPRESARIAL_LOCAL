from pathlib import Path
import sys

def check(name,cond):
    if not cond:
        print(f'FAIL {name}')
        raise AssertionError(name)
    print(f'PASS {name}')

if len(sys.argv)<2:
    raise SystemExit('Uso: python test_r10_13d17_e2e_type_aware_drill_sorting.py <dashboard.html>')
p=Path(sys.argv[1])
t=p.read_text(encoding='utf-8',errors='replace')
print('\n=== R10.13D.17 E2E TYPE-AWARE DRILL-THROUGH SORTING ===')
print(f'Archivo: {p}')
check('dimension_profitability_present','"operator":"dimension_profitability"' in t)
check('transaction_table_present','"operator":"transaction_table"' in t)
check('d13_csv_preserved','function exportDrillThroughCsv()' in t)
check('d14_provenance_preserved','Fórmula y provenance' in t)
check('d15_audit_preserved','function drillThroughAuditSnapshot()' in t)
check('d16_search_preserved','id="r13bDrillThroughSearch"' in t)
check('d16_pagination_preserved','const drillThroughPageSize=100;' in t)
check('d17_sort_state',"let drillThroughSortColumn=null;" in t and "let drillThroughSortDirection='asc';" in t)
check('d17_type_compare','function drillThroughCompareValues(' in t)
check('d17_numeric_sort','Number.isFinite(an)' in t)
check('d17_date_sort','Date.parse(a)-Date.parse(b)' in t)
check('d17_locale_sort','localeCompare(' in t and "'es-MX'" in t)
check('d17_sort_headers','data-r13b-drill-sort' in t)
check('d17_stable_sort','left.index-right.index' in t)
check('product_id_preserved','"product_id":"Cod_Articulo"' in t)
check('seller_id_preserved','"seller_id":"Cod_Vendedor"' in t)
check('freight_still_blocked','"id":"kpi:freight"' in t and '"status":"BLOCKED"' in t)
check('coverage_still_93_94','"percent":93.94' in t or '"coverage_pct":93.94' in t)
check('profit_rule_present','universal.profit.revenue_minus_cost.v1' in t)
check('margin_rule_present','universal.margin_pct.revenue_cost_over_revenue.v1' in t)
print('\nPASS R10.13D.17 E2E TYPE-AWARE DRILL-THROUGH SORTING')
