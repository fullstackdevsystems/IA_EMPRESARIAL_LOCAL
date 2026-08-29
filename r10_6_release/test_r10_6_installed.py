import sys
from pathlib import Path
import pandas as pd
root=Path(sys.argv[1]).resolve(); sys.path.insert(0,str(root/'scripts'))
from enterprise_ai.analytic_rules import evaluate_analytic_context
import bi_productivo as bi

def b(t,target,expr,rid):
    return {'rule_type':t,'target':target,'priority':100,'rule':{'id':rid,'name':rid,'version':2,'expression':expr,'source_type':'test','source_ref':'r10.6'}}

df=pd.DataFrame([
 {'Estado':'A','MontoNeto':100.0,'CostoReal':70.0,'FleteReal':5.0,'Cantidad':10},
 {'Estado':'X','MontoNeto':200.0,'CostoReal':100.0,'FleteReal':20.0,'Cantidad':20},
])
roles={'revenue':'MontoNeto','total_cost':'CostoReal','freight':'FleteReal','quantity':'Cantidad'}
ctx={'version':'r10.6','bindings':[b('row_filter','sales_valid','Estado == "A"','VENTA_VALIDA'),b('metric','profit','MontoNeto - CostoReal - FleteReal','UTILIDAD_REAL')]}
r=evaluate_analytic_context(df,roles,ctx)
assert len(r['frame'])==1 and float(r['metrics']['profit'].iloc[0])==25.0 and not r['errors']
work,derived,notes=bi.prepare_business(df,roles,ctx)
assert len(work)==1 and round(float(work['_utilidad'].sum()),2)==25.0
assert derived.get('reglas_filtro') and derived.get('reglas_metricas')
assert '8.5.5-r10.6-analytic-rules' in (root/'VERSION.txt').read_text(errors='ignore')
print('PASS installed_validated_filter')
print('PASS installed_validated_profit')
print('PASS installed_bi_provenance')
print('3/3 PASS R10.6 INSTALLED INTEGRATION')
