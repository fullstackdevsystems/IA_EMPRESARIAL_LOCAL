import sys, types
from pathlib import Path
import pandas as pd

# Stubs mínimos para importar el módulo sin construir persistencia.
pkg=types.ModuleType('enterprise_ai'); pkg.__path__=[str(Path(__file__).parent)]; sys.modules['enterprise_ai']=pkg
for name, attrs in {
    'database': {'Database': object, 'utcnow': lambda:'2026-01-01T00:00:00+00:00'},
    'knowledge_governance': {'KnowledgeGovernance': object},
    'precedence_engine': {'PrecedenceEngine': object},
    'security': {'Principal': object, 'scope_clause': lambda p,a='': ('1=1',())},
}.items():
    m=types.ModuleType('enterprise_ai.'+name)
    for k,v in attrs.items(): setattr(m,k,v)
    sys.modules['enterprise_ai.'+name]=m

# semantic_registry real necesita precedence/security, ya stubbeados.
import importlib.util
spec=importlib.util.spec_from_file_location('enterprise_ai.semantic_registry',Path(__file__).parent/'semantic_registry.py')
sem=importlib.util.module_from_spec(spec); sys.modules['enterprise_ai.semantic_registry']=sem; spec.loader.exec_module(sem)
spec=importlib.util.spec_from_file_location('enterprise_ai.analytic_rules',Path(__file__).parent/'analytic_rules.py')
ar=importlib.util.module_from_spec(spec); sys.modules['enterprise_ai.analytic_rules']=ar; spec.loader.exec_module(ar)

def ctx(bindings): return {'version':'r10.6','bindings':bindings}
def b(t,target,expr,name='R',rid='r1'):
    return {'rule_type':t,'target':target,'priority':100,'rule':{'id':rid,'name':name,'version':2,'expression':expr,'source_type':'user','source_ref':'test'}}

def run():
    df=pd.DataFrame([
        {'Estatus':'A','Venta':100.0,'Costo':70.0,'Flete':5.0,'Ton':10},
        {'Estatus':'X','Venta':200.0,'Costo':100.0,'Flete':20.0,'Ton':20},
        {'Estatus':'A','Venta':50.0,'Costo':60.0,'Flete':3.0,'Ton':0},
    ])
    roles={'revenue':'Venta','total_cost':'Costo','freight':'Flete','quantity':'Ton'}
    r=ar.evaluate_analytic_context(df,roles,ctx([b('row_filter','sales_valid','Estatus == "A"')]))
    assert len(r['frame'])==2 and r['rows_output']==2 and not r['errors']
    print('PASS validated_row_filter_before_aggregation')

    r=ar.evaluate_analytic_context(df,roles,ctx([b('metric','profit','Venta - Costo - Flete','UTILIDAD_REAL')]))
    assert list(r['metrics']['profit'].round(2))==[25.0,80.0,-13.0]
    print('PASS validated_profit_metric')

    r=ar.evaluate_analytic_context(df,roles,ctx([
        b('row_filter','sales_valid','Estatus == "A"','VENTA_VALIDA','f1'),
        b('metric','profit','Venta - Costo - Flete','UTILIDAD_REAL','m1')]))
    assert len(r['frame'])==2 and list(r['metrics']['profit'].round(2))==[25.0,-13.0]
    print('PASS filter_then_metric_order')

    r=ar.evaluate_analytic_context(df,roles,ctx([b('metric','unit_profit','(Venta - Costo) / Ton')]))
    vals=r['metrics']['unit_profit']; assert round(float(vals.iloc[0]),2)==3.0 and pd.isna(vals.iloc[2])
    print('PASS safe_division_by_zero')

    r=ar.evaluate_analytic_context(df,roles,ctx([b('metric','profit','Venta - CampoInexistente')]))
    assert r['errors'] and r['errors'][0]['stage']=='metric' and 'CampoInexistente' in r['errors'][0]['error']
    print('PASS missing_required_column_is_explicit')

    r=ar.evaluate_analytic_context(df,roles,ctx([b('metric','profit','__import__("os").system("echo hacked")')]))
    assert r['errors'] and 'no permitida' in r['errors'][0]['error'].lower()
    print('PASS arbitrary_code_blocked')

    r=ar.evaluate_analytic_context(df,roles,ctx([b('row_filter','positive_sales','Venta > 75 and Costo >= 70')]))
    assert len(r['frame'])==2
    print('PASS boolean_comparison_rules')

    print('7/7 PASS R10.6 ANALYTIC RULE ENGINE')

if __name__=='__main__': run()
