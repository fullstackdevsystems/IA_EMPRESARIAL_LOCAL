import sys, tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))

# Load traceability with small enterprise_ai stubs through actual package fixture.
import types
pkg=types.ModuleType('enterprise_ai'); pkg.__path__=[]; sys.modules['enterprise_ai']=pkg

dbmod=types.ModuleType('enterprise_ai.database')
import sqlite3, json
from contextlib import contextmanager
from datetime import datetime, timezone

def utcnow(): return datetime.now(timezone.utc).isoformat()
class DB:
    def __init__(self,p): self.p=p; self.con=sqlite3.connect(p); self.con.row_factory=sqlite3.Row
    @contextmanager
    def tx(self):
        try: yield self.con; self.con.commit()
        except: self.con.rollback(); raise
    def execute(self,s,p=()): self.con.execute(s,tuple(p)); self.con.commit()
    def one(self,s,p=()): return self.con.execute(s,tuple(p)).fetchone()
    def query(self,s,p=()): return self.con.execute(s,tuple(p)).fetchall()
    def audit(self,*a,**k): pass
dbmod.Database=DB; dbmod.utcnow=utcnow; sys.modules['enterprise_ai.database']=dbmod
sec=types.ModuleType('enterprise_ai.security')
class Principal:
    def __init__(self,c,u,role='user'): self.company_id=c; self.user_id=u; self.role=role
sec.Principal=Principal; sec.scope_clause=lambda p,alias='':('',()); sys.modules['enterprise_ai.security']=sec

import importlib.util
spec=importlib.util.spec_from_file_location('enterprise_ai.traceability',Path(__file__).with_name('traceability.py')); m=importlib.util.module_from_spec(spec); sys.modules['enterprise_ai.traceability']=m; spec.loader.exec_module(m)

with tempfile.TemporaryDirectory() as td:
    db=DB(str(Path(td)/'x.db')); tm=m.TraceabilityManager(db); a=Principal('A','u1'); b=Principal('B','u1')
    with tm.scope(a,trace_type='chat',target_ref='req1',prompt='ventas secretas') as tid:
        m.trace_step('semantic_resolution',engine='SemanticRegistry',details={'validated_count':2,'inferred_count':1})
        m.trace_step('structured_calculation',engine='python/pandas',details={'file':'ventas.xlsx','sheet':'BD','rows_used':120,'calculation':'python/pandas','token':'NO_GUARDAR'})
        m.trace_step('analytic_rules',engine='SafeRuleEvaluator',details={'filters_count':1,'metrics_count':1,'rows_input':120,'rows_output':110})
        m.trace_step('llm_interpretation',engine='ollama/qwen')
    t=tm.get(a,tid); assert len(t['steps'])==4 and t['status']=='completed'; print('PASS persistent_trace')
    assert t['steps'][1]['details']['token']=='[REDACTED]'; print('PASS sensitive_redaction')
    try: tm.get(b,tid); raise AssertionError('leak')
    except KeyError: pass
    print('PASS company_isolation')
    e=tm.explain(a,tid); assert 'python/pandas' in e['explanation'] and 'filas 120→110' in e['explanation']; print('PASS human_explanation')
    ft=m.build_file_trace(filename='x.xlsx',sheet='BD',rows=5,columns=['Venta'],roles={'revenue':'Venta'},prompt='analiza'); assert ft['calculation_engine']=='python/pandas' and 'prompt_hash' in ft; print('PASS file_manifest')
    d=m.sanitize_details({'password':'abc','prompt':'texto','nested':{'api_key':'x'}}); assert d['password']=='[REDACTED]' and 'prompt_sha256' in d and d['nested']['api_key']=='[REDACTED]'; print('PASS generic_sanitization')
print('6/6 PASS R10.9 TRACEABILITY')
