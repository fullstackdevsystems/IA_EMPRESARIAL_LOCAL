from __future__ import annotations

import importlib
import sqlite3
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path

import pandas as pd

HERE=Path(__file__).resolve().parent


def build_isolated_package(td: Path):
    pkg=td/'enterprise_ai'; pkg.mkdir()
    (pkg/'__init__.py').write_text('',encoding='utf-8')
    (pkg/'database.py').write_text('''\nimport sqlite3\nfrom contextlib import contextmanager\nfrom datetime import datetime, timezone\n\ndef utcnow(): return datetime.now(timezone.utc).isoformat()\nclass Database:\n    def __init__(self,path): self.path=str(path)\n    def connect(self):\n        c=sqlite3.connect(self.path); c.row_factory=sqlite3.Row; return c\n    @contextmanager\n    def tx(self):\n        c=self.connect()\n        try:\n            yield c; c.commit()\n        except Exception:\n            c.rollback(); raise\n        finally: c.close()\n    def execute(self,sql,params=()):\n        with self.tx() as c: c.execute(sql,tuple(params))\n    def query(self,sql,params=()):\n        c=self.connect()\n        try:return list(c.execute(sql,tuple(params)).fetchall())\n        finally:c.close()\n    def one(self,sql,params=()):\n        r=self.query(sql,params); return r[0] if r else None\n    def audit(self,*a,**k): pass\n''',encoding='utf-8')
    (pkg/'security.py').write_text('''\nfrom dataclasses import dataclass\n@dataclass(frozen=True)\nclass Principal:\n    company_id:str\n    user_id:str\n    role:str='user'\ndef scope_clause(principal,alias=''):\n    p=(alias+'.') if alias else ''\n    return f"{p}company_id=? AND ({p}scope='company' OR {p}user_id=?)", (principal.company_id,principal.user_id)\n''',encoding='utf-8')
    (pkg/'knowledge_governance.py').write_text((HERE/'knowledge_governance.py').read_text(encoding='utf-8'),encoding='utf-8')
    (pkg/'precedence_engine.py').write_text((HERE/'precedence_engine.py').read_text(encoding='utf-8'),encoding='utf-8')
    sys.path.insert(0,str(td))
    return importlib.import_module('enterprise_ai.database'), importlib.import_module('enterprise_ai.security'), importlib.import_module('enterprise_ai.knowledge_governance'), importlib.import_module('enterprise_ai.precedence_engine')


def run():
    with tempfile.TemporaryDirectory() as raw:
        td=Path(raw)
        dbm,secm,kgm,pem=build_isolated_package(td)
        db=dbm.Database(td/'db.sqlite3')
        gov=kgm.KnowledgeGovernance(db)
        eng=pem.PrecedenceEngine(gov)
        a=secm.Principal('EMPRESA_A','admin','admin')
        b=secm.Principal('EMPRESA_B','admin','admin')

        # 1 semantic validated overrides heuristic role
        d=gov.propose_semantic_definition(a,physical_name='MontoNeto',semantic_name='venta_neta',area='Ventas')
        gov.validate_semantic_definition(a,d['id'])
        roles,applied=eng.semantic_overrides(a,['MontoNeto','CostoReal'],{'sales':'OtraColumna'})
        assert roles['sales']=='MontoNeto' and applied and applied[0]['precedence']=='validated_semantic_definition'
        print('PASS validated_semantic_overrides_inference')

        # 2 isolation
        roles_b,applied_b=eng.semantic_overrides(b,['MontoNeto'],{'sales':None})
        assert roles_b.get('sales') is None and applied_b==[]
        print('PASS semantic_company_isolation')

        # 3 validated rule wins and applies temporal validity
        r=gov.propose_rule(a,name='UTILIDAD_REAL',expression='Venta - Costo - Flete',area='Ventas',valid_from='2026-01-01')
        gov.validate_rule(a,r['id'])
        picked=eng.rule_for_metric(a,'profit',question='calcula utilidad real',area='Ventas',on_date='2026-08-01')
        assert picked and picked['id']==r['id']
        assert eng.rule_for_metric(a,'profit',question='utilidad',area='Ventas',on_date='2025-08-01') is None
        print('PASS validated_rule_temporal_precedence')

        # 4 deterministic safe calculation
        df=pd.DataFrame({'Venta':[1000,500],'Costo':[700,450],'Flete':[100,20]})
        result=eng.evaluate_rule(df,{'sales':'Venta','cost':'Costo','freight':'Flete'},picked)
        assert result.tolist()==[200,30]
        print('PASS deterministic_validated_rule_calculation')

        # 5 arbitrary code is blocked
        evil=dict(picked); evil['expression']='__import__("os").system("echo hacked")'
        try:
            eng.evaluate_rule(df,{'sales':'Venta','cost':'Costo','freight':'Flete'},evil)
            raise AssertionError('unsafe expression was accepted')
        except ValueError:
            pass
        print('PASS unsafe_rule_expression_blocked')

        # 6 conflict remains enforced
        r2=gov.propose_rule(a,name='UTILIDAD_REAL',expression='Venta - Costo',area='Ventas',valid_from='2026-01-01')
        try:
            gov.validate_rule(a,r2['id'])
            raise AssertionError('conflict not blocked')
        except ValueError as exc:
            assert 'CONFLICTO' in str(exc)
        print('PASS validated_rule_conflict_blocked')

        # 7 precedence order is explicit
        ctx=eng.knowledge_context(a,'calcula utilidad',columns=['MontoNeto','CostoReal'],inferred_roles={'sales':'Otra'})
        assert ctx['precedence'][0]=='validated_business_rule'
        assert ctx['precedence'][1]=='validated_semantic_definition'
        assert ctx['rules']
        print('PASS explicit_precedence_chain')

        # 8 R10.3 duplicate proposal snapshot bug fixed: one create snapshot
        d2=gov.propose_semantic_definition(a,physical_name='Cve_Clie',semantic_name='cliente_id')
        rows=db.query("SELECT * FROM knowledge_governance_history WHERE object_type='semantic_definition' AND object_id=? AND reason='create_proposal'",(d2['id'],))
        assert len(rows)==1
        print('PASS governance_history_deduplicated')

        print('8/8 PASS R10.4 ENTERPRISE PRECEDENCE')

if __name__=='__main__': run()
