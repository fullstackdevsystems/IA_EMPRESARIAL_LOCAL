from __future__ import annotations
import sys, tempfile
from pathlib import Path
import pandas as pd

HERE=Path(__file__).resolve().parent
# Fake package dependencies are supplied by installed project in integration tests.


def run_unit(root: Path):
    sys.path.insert(0,str(root/'scripts'))
    from enterprise_ai.database import Database
    from enterprise_ai.security import Principal
    from enterprise_ai.knowledge_governance import KnowledgeGovernance
    from enterprise_ai.precedence_engine import PrecedenceEngine
    from enterprise_ai.semantic_registry import SemanticRegistry, merge_context_roles, current_context

    db=Database(root/'data'/'enterprise'/'r10_5_test.sqlite3')
    gov=KnowledgeGovernance(db)
    prec=PrecedenceEngine(gov)
    reg=SemanticRegistry(prec)
    a=Principal('EMPRESA_A','u1','admin'); b=Principal('EMPRESA_B','u2','admin')

    # APIs de governance varían ligeramente por build; usar las firmas del R10.3/4 instalado.
    d=gov.propose_semantic_definition(a,physical_name='MontoNeto',semantic_name='venta_neta',area='Ventas',source_type='test')
    gov.validate_semantic_definition(a,d['id'])
    df=pd.DataFrame({'MontoNeto':[10,20], 'CostoX':[7,8], 'ClienteX':['A','B']})
    ctx=reg.resolve_frame(a,df,{'revenue':'CostoX'})
    assert ctx['roles']['revenue']=='MontoNeto'
    print('PASS validated_dictionary_overrides_bi_inference')

    ctxb=reg.resolve_frame(b,df,{'revenue':'CostoX'})
    assert ctxb['roles']['revenue']=='CostoX'
    print('PASS company_isolation_semantic_registry')

    legacy=merge_context_roles({'sales':'MontoNeto','cost':'CostoX'},None)
    assert legacy['revenue']=='MontoNeto' and legacy['total_cost']=='CostoX'
    print('PASS cross_engine_role_bridge')

    with reg.bind(a,df,{'sales':'CostoX'}) as bound:
        assert current_context()['roles']['revenue']=='MontoNeto'
        assert bound['company_id']=='EMPRESA_A'
    assert current_context() is None
    print('PASS scoped_semantic_context_no_leak')

    # No definición: inferencia queda intacta.
    plain=pd.DataFrame({'Ventas':[1,2]})
    c=reg.resolve_frame(a,plain,{'revenue':'Ventas'})
    assert c['roles']['revenue']=='Ventas'
    print('PASS inference_fallback_when_no_validated_definition')

    print('5/5 PASS R10.5 SEMANTIC REGISTRY')

if __name__=='__main__':
    if len(sys.argv)!=2: raise SystemExit('Uso: python test_r10_5_semantics.py C:\\ruta\\IA_Local')
    run_unit(Path(sys.argv[1]).resolve())
