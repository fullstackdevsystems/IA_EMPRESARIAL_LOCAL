from __future__ import annotations
from pathlib import Path
import sys
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
SCRIPTS=ROOT/'scripts'
sys.path.insert(0,str(SCRIPTS))

from capability_rules import RULESET_VERSION, DERIVED_METRIC_RULES, evaluate_rule
from dashboard_spec_builder import build_dashboard_spec
from dynamic_renderer import attach_dynamic_renderer, build_dynamic_renderer_model, runtime_markup


def cap(spec, cid):
    return next(x for x in spec['components'] if x['id']==cid)


df=pd.DataFrame({
    'Fecha':['2026-01-01','2026-01-02','2026-01-03'],
    'Cliente':['A','A','B'],
    'Cod_Cliente':['C1','C1','C2'],
    'Articulo':['P1','P2','P1'],
    'Vendedor':['V1','V2','V1'],
    'Refer':['R1','R2','R3'],
    'Importe_Venta':[100.0,200.0,50.0],
    'Costo':[60.0,120.0,40.0],
    'Toneladas_Vendidas':[10.0,20.0,5.0],
    'Costo_Flete':[10.0,20.0,5.0],
})
roles={
    'date':'Fecha','customer':'Cliente','customer_id':'Cod_Cliente','product':'Articulo','seller':'Vendedor',
    'transaction_id':'Refer','revenue':'Importe_Venta','cost':'Costo','quantity':'Toneladas_Vendidas',
}
prompt='''Genera un dashboard de ventas con utilidad, margen %, utilidad por tonelada, precio por tonelada, costo por tonelada, número de operaciones, ticket promedio, clientes activos, vendedores activos y productos vendidos.'''
spec=build_dashboard_spec(df,prompt,sheet='Datos',semantic_roles=roles)

expected={
 'kpi:profit':'universal.profit.revenue_minus_cost.v1',
 'kpi:margin_pct':'universal.margin_pct.revenue_cost_over_revenue.v1',
 'kpi:profit_per_unit':'universal.profit_per_unit.revenue_cost_over_quantity.v1',
 'kpi:price_per_unit':'universal.price_per_unit.revenue_over_quantity.v1',
 'kpi:cost_per_unit':'universal.cost_per_unit.cost_over_quantity.v1',
 'kpi:operations':'universal.operations.nunique_transaction.v1',
 'kpi:ticket_avg':'universal.ticket_avg.revenue_over_operations.v1',
 'kpi:active_customers':'universal.active_customers.nunique_customer_id.v1',
 'kpi:active_sellers':'universal.active_sellers.nunique_seller.v1',
 'kpi:products_sold':'universal.products_sold.nunique_product.v1',
}

checks=[]
checks.append(('ruleset_version',RULESET_VERSION=='r10.13c' and spec['provenance']['ruleset_version']=='r10.13c'))
checks.append(('registry_has_core_rules',all(k.split(':',1)[1] in DERIVED_METRIC_RULES for k in expected)))
for cid,rule_id in expected.items():
    c=cap(spec,cid)
    checks.append((cid+'_derivable',c['status']=='DERIVABLE'))
    checks.append((cid+'_rule_id',c.get('rule',{}).get('rule_id')==rule_id))
    checks.append((cid+'_execution',bool(c.get('execution',{}).get('operator')) and c.get('execution',{}).get('zero_division')=='N/D'))
    checks.append((cid+'_provenance',c.get('provenance',{}).get('source')=='capability_rule_registry'))

expected_values={
 'kpi:profit':130.0,
 'kpi:margin_pct':100.0*130.0/350.0,
 'kpi:profit_per_unit':130.0/35.0,
 'kpi:price_per_unit':350.0/35.0,
 'kpi:cost_per_unit':220.0/35.0,
 'kpi:operations':3.0,
 'kpi:ticket_avg':350.0/3.0,
 'kpi:active_customers':2.0,
 'kpi:active_sellers':2.0,
 'kpi:products_sold':2.0,
}
for cid,value in expected_values.items():
    got=evaluate_rule(df,cap(spec,cid))
    checks.append((cid+'_numeric',got is not None and abs(got-value)<1e-9))

zero_df=df.copy(); zero_df['Toneladas_Vendidas']=0.0
checks.append(('zero_division_python_nd',evaluate_rule(zero_df,cap(spec,'kpi:profit_per_unit')) is None))

# Missing dependencies must block rather than invent.
df_missing=pd.DataFrame({'Importe_Venta':[100.0,200.0]})
spec_missing=build_dashboard_spec(df_missing,'margen % y utilidad por tonelada',semantic_roles={'revenue':'Importe_Venta'})
checks.append(('margin_missing_blocked',cap(spec_missing,'kpi:margin_pct')['status']=='BLOCKED'))
checks.append(('profit_per_unit_missing_blocked',cap(spec_missing,'kpi:profit_per_unit')['status']=='BLOCKED'))

# Freight per unit is allowed only when freight itself is an actual semantic role.
spec_freight_direct=build_dashboard_spec(df,'flete por tonelada',semantic_roles={'freight':'Costo_Flete','quantity':'Toneladas_Vendidas'})
checks.append(('freight_per_unit_direct_derivable',cap(spec_freight_direct,'kpi:freight_per_unit')['status']=='DERIVABLE'))
checks.append(('freight_per_unit_rule',cap(spec_freight_direct,'kpi:freight_per_unit').get('rule',{}).get('rule_id')=='universal.freight_per_unit.freight_over_quantity.v1'))

spec_freight_block=build_dashboard_spec(df.drop(columns=['Costo_Flete']),'flete por tonelada',semantic_roles={'quantity':'Toneladas_Vendidas'})
checks.append(('freight_per_unit_without_freight_blocked',cap(spec_freight_block,'kpi:freight_per_unit')['status']=='BLOCKED'))

# Direct profit must win over derivation.
spec_direct_profit=build_dashboard_spec(df.assign(Utilidad=[40.0,80.0,10.0]),'utilidad',semantic_roles={'profit':'Utilidad','revenue':'Importe_Venta','cost':'Costo'})
checks.append(('direct_profit_supported',cap(spec_direct_profit,'kpi:profit')['status']=='SUPPORTED'))

# Renderer consumes operators/rules and zero division returns N/D (null), not fabricated zero.
model=build_dynamic_renderer_model(spec,{})
rt=runtime_markup()
checks.append(('renderer_c_version',model['version']=='r10.13c'))
checks.append(('renderer_ruleset',model['ruleset_version']=='r10.13c'))
checks.append(('renderer_operator_executor',"op==='difference_of_sums'" in rt and "op==='sum_over_nunique'" in rt))
checks.append(('renderer_zero_division_nd',"return den?sum(rr,cols[0])/den:null" in rt and "división por cero: N/D" in rt))
checks.append(('renderer_legacy_derived_host','Métricas derivadas gobernadas' in rt))

plan={'execution_plan':{'dashboard_spec':spec,'requested_count':999,'coverage_pct':100},'kpis':[],'charts':[],'filters':[]}
attach_dynamic_renderer(plan)
exec_c=next(x for x in plan['execution_plan']['components'] if x['key']=='kpi:margin_pct')
checks.append(('canonical_plan_rule',exec_c.get('rule',{}).get('rule_id')==expected['kpi:margin_pct']))
checks.append(('canonical_plan_execution',exec_c.get('execution',{}).get('operator')=='difference_over_sum_pct'))
checks.append(('canonical_plan_authority',plan['execution_plan'].get('authority')=='dashboard_spec'))

failed=[]
for name,ok in checks:
    print(('PASS' if ok else 'FAIL'),name)
    if not ok: failed.append(name)
print(f"{len(checks)-len(failed)}/{len(checks)} PASS R10.13C DERIVED METRICS + CAPABILITY RULES")
if failed:
    raise SystemExit('FAILED: '+', '.join(failed))
