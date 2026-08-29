from __future__ import annotations
import sys, tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))

# Stubs minimalistas para probar FeedbackManager sin cargar la app completa.
class Principal:
    def __init__(self,company_id,user_id): self.company_id=company_id; self.user_id=user_id

# Importa feedback con stubs de package usando copia temporal de dependencias minimas.
import types, sqlite3, json
pkg=types.ModuleType('enterprise_ai'); pkg.__path__=[]; sys.modules['enterprise_ai']=pkg
sec=types.ModuleType('enterprise_ai.security'); sec.Principal=Principal; sec.scope_clause=lambda p,alias='': ('company_id=? AND (scope=\'company\' OR user_id=?)',(p.company_id,p.user_id)); sys.modules['enterprise_ai.security']=sec
class DB:
    def __init__(self,p): self.p=p; self.c=sqlite3.connect(p); self.c.row_factory=sqlite3.Row; self.c.execute('pragma foreign_keys=on')
    class TX:
        def __init__(self,db):self.db=db
        def __enter__(self):return self.db.c
        def __exit__(self,*a):self.db.c.commit()
    def tx(self):return DB.TX(self)
    def execute(self,s,p=()):self.c.execute(s,p);self.c.commit()
    def one(self,s,p=()):return self.c.execute(s,p).fetchone()
    def query(self,s,p=()):return list(self.c.execute(s,p).fetchall())
    def audit(self,*a,**k):pass
mod=types.ModuleType('enterprise_ai.database'); mod.Database=DB; mod.utcnow=lambda:'2026-08-29T00:00:00+00:00';sys.modules['enterprise_ai.database']=mod
import importlib.util
spec=importlib.util.spec_from_file_location('enterprise_ai.feedback',Path(__file__).with_name('feedback.py')); fm=importlib.util.module_from_spec(spec);sys.modules['enterprise_ai.feedback']=fm;spec.loader.exec_module(fm)
class Gov:
    def __init__(self):self.rules={};self.sem={}
    def propose_rule(self,p,**k):i='r'+str(len(self.rules)+1);x={'id':i,'status':'PROPUESTO',**k};self.rules[i]=x;return x
    def validate_rule(self,p,i,replace_conflicts=False):self.rules[i]['status']='VALIDADO';return self.rules[i]
    def reject_rule(self,p,i):self.rules[i]['status']='RECHAZADO';return self.rules[i]
    def propose_semantic_definition(self,p,**k):i='s'+str(len(self.sem)+1);x={'id':i,'status':'PROPUESTO',**k};self.sem[i]=x;return x
    def validate_semantic_definition(self,p,i,replace_conflicts=False):self.sem[i]['status']='VALIDADO';return self.sem[i]
    def reject_semantic_definition(self,p,i):self.sem[i]['status']='RECHAZADO';return self.sem[i]
class Mem:
    def __init__(self):self.m={}
    def create(self,p,c,cat,**k):i='m'+str(len(self.m)+1);x={'id':i,'status':k.get('status')};self.m[i]=x;return x
    def confirm(self,p,i):self.m[i]['status']='active';return self.m[i]
    def forget(self,p,i):self.m[i]['status']='forgotten'

def run():
    with tempfile.TemporaryDirectory() as td:
        db=DB(str(Path(td)/'x.db')); f=fm.FeedbackManager(db,Mem(),Gov()); p=Principal('A','u')
        a=f.submit(p,feedback_type='CORRECTO',target_ref='req1',original_text='ok'); assert a['proposal_type']=='none'
        print('PASS positive_feedback_no_learning')
        b=f.submit(p,feedback_type='REQUIERE_CORRECCION',correction_text='Utilidad = Venta - Costo - Flete',proposal_name='UTILIDAD_REAL'); assert b['proposal_status']=='PROPUESTO' and b['proposal']['status']=='PROPUESTO'
        print('PASS correction_creates_proposal_not_validation')
        bv=f.validate_proposal(p,b['id']); assert bv['proposal_status']=='VALIDADO'
        print('PASS explicit_validation_required')
        c=f.submit(p,feedback_type='REQUIERE_CORRECCION',correction_text='Cve_Clie significa cliente_id'); assert c['proposal_type']=='semantic'
        print('PASS semantic_correction_detection')
        d=f.submit(p,feedback_type='REQUIERE_CORRECCION',correction_text='Preferimos agrupar primero por sucursal'); assert d['proposal_type']=='memory' and d['proposal']['status']=='pending'
        print('PASS generic_correction_pending_memory')
        e=f.submit(p,feedback_type='REQUIERE_CORRECCION',correction_text='Venta = Importe',proposal_name='VENTA'); f.reject_proposal(p,e['id']); assert f.get(p,e['id'])['proposal_status']=='RECHAZADO'
        print('PASS explicit_rejection')
        p2=Principal('B','u'); assert f.list(p2)==[]
        print('PASS company_isolation')
        print('7/7 PASS R10.8 FEEDBACK')
if __name__=='__main__':run()
