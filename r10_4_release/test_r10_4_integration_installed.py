from __future__ import annotations
import inspect, tempfile
from pathlib import Path
import pandas as pd
from enterprise_ai.database import Database
from enterprise_ai.security import Principal
from enterprise_ai.knowledge_governance import KnowledgeGovernance
from enterprise_ai.precedence_engine import PrecedenceEngine
from enterprise_ai.structured_data import StructuredDataService
from enterprise_ai.context_engine import ContextEngine
import enterprise_ai.factory as factory


def main():
    sig=inspect.signature(StructuredDataService.__init__)
    assert 'governance' in sig.parameters and 'precedence' in sig.parameters
    print('PASS structured_data_accepts_governance')
    sig2=inspect.signature(ContextEngine.__init__)
    assert 'governance' in sig2.parameters and 'precedence' in sig2.parameters
    print('PASS context_engine_accepts_precedence')
    src=inspect.getsource(factory.build_components)
    assert 'PrecedenceEngine(governance)' in src and 'precedence=precedence' in src
    print('PASS factory_wires_precedence')
    with tempfile.TemporaryDirectory() as td:
        db=Database(Path(td)/'enterprise.db')
        gov=KnowledgeGovernance(db); eng=PrecedenceEngine(gov)
        p=Principal('TESTCO','admin','admin')
        d=gov.propose_semantic_definition(p,physical_name='MontoNeto',semantic_name='venta_neta')
        gov.validate_semantic_definition(p,d['id'])
        roles,items=eng.semantic_overrides(p,['MontoNeto','CostoReal'],{'sales':'wrong'})
        assert roles['sales']=='MontoNeto' and items
        print('PASS validated_semantic_precedence')
        r=gov.propose_rule(p,name='UTILIDAD_REAL',expression='Venta - Costo - Flete',area='Ventas',valid_from='2026-01-01')
        gov.validate_rule(p,r['id'])
        chosen=eng.rule_for_metric(p,'profit',question='utilidad real',on_date='2026-08-01')
        df=pd.DataFrame({'Venta':[1000.0],'Costo':[700.0],'Flete':[100.0]})
        out=eng.evaluate_rule(df,{'sales':'Venta','cost':'Costo','freight':'Flete'},chosen)
        assert float(out.iloc[0])==200.0
        print('PASS validated_rule_deterministic_calculation')
        evil=dict(chosen); evil['expression']='__import__("os").system("calc")'
        try: eng.evaluate_rule(df,{'sales':'Venta'},evil); raise AssertionError('unsafe')
        except ValueError: pass
        print('PASS arbitrary_code_blocked')
        ctx=eng.knowledge_context(p,'utilidad real')
        assert ctx['precedence'][:2]==['validated_business_rule','validated_semantic_definition']
        print('PASS precedence_order')
        d2=gov.propose_semantic_definition(p,physical_name='Cve_Clie',semantic_name='cliente_id')
        hist=db.query("SELECT * FROM knowledge_governance_history WHERE object_type='semantic_definition' AND object_id=? AND reason='create_proposal'",(d2['id'],))
        assert len(hist)==1
        print('PASS governance_history_clean')
    print('8/8 PASS R10.4 ENTERPRISE PRECEDENCE')
if __name__=='__main__': main()
