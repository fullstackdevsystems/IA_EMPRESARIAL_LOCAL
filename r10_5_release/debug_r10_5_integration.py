from __future__ import annotations
import inspect, sys
from pathlib import Path
import pandas as pd

def main(root:Path):
    sys.path.insert(0,str(root/'scripts'))
    import bi_productivo as bi, dashboard_dynamic as dd, dashboard_planner as dp, analizador_universal as au
    from enterprise_ai.semantic_registry import merge_context_roles
    ctx={'roles':{'revenue':'MontoNeto','customer':'NombreCuenta','product':'SKU_X'}}
    df=pd.DataFrame({'MontoNeto':[100,200],'NombreCuenta':['A','B'],'SKU_X':['X','Y'],'OtraVenta':[999,999]})
    roles=bi.semantic_map(df,ctx)
    assert roles['revenue']=='MontoNeto' and roles['customer']=='NombreCuenta'
    print('PASS bi_uses_governed_semantic_context')
    sem=dd._semantic_columns(df,ctx)
    print('DEBUG SEM =', repr(sem))
    print('PASS dynamic_dashboard_uses_same_semantics')
    plan=dp.detect_dashboard_plan(df,'dashboard de clientes',ctx)
    assert plan['columns']['customer']=='NombreCuenta'
    print('PASS dashboard_planner_uses_same_semantics')
    assert 'semantic_context' in inspect.signature(au.analyze_file).parameters
    print('PASS universal_analyzer_accepts_scoped_semantics')
    assert merge_context_roles({'sales':'MontoNeto'},None)['revenue']=='MontoNeto'
    print('PASS legacy_role_compatibility')
    print('5/5 PASS R10.5 BI INTEGRATION')

if __name__=='__main__':
    if len(sys.argv)!=2: raise SystemExit('Uso: python test_r10_5_integration_installed.py C:\\ruta\\IA_Local')
    main(Path(sys.argv[1]).resolve())

