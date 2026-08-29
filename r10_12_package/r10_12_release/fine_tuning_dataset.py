from __future__ import annotations
import hashlib, json, re, uuid
from pathlib import Path
from typing import Any, Dict, List, Optional
from .database import Database, utcnow
from .security import Principal, scope_clause

VERSION='8.5.5-r10.12-controlled-finetune-dataset'
EXPORT_FORMATS={'jsonl','alpaca_jsonl'}
SECRET_RE=re.compile(r'(?i)\b(password|contrase(?:ña|na)|api[_ -]?key|token|secreto|private[_ -]?key|clave privada|cvv|nip)\b')
EMAIL_RE=re.compile(r'\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b',re.I)
PHONE_RE=re.compile(r'(?<!\d)(?:\+?52[\s.-]?)?(?:\(?\d{2,3}\)?[\s.-]?)?\d{3}[\s.-]?\d{4}(?!\d)')
SCHEMA=r'''
CREATE TABLE IF NOT EXISTS finetune_dataset_runs(id TEXT PRIMARY KEY,company_id TEXT NOT NULL,user_id TEXT NOT NULL,status TEXT NOT NULL,source_count INTEGER NOT NULL DEFAULT 0,approved_count INTEGER NOT NULL DEFAULT 0,rejected_count INTEGER NOT NULL DEFAULT 0,export_format TEXT,export_path TEXT,sha256 TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_finetune_runs_company ON finetune_dataset_runs(company_id,created_at);
CREATE TABLE IF NOT EXISTS finetune_examples(id TEXT PRIMARY KEY,run_id TEXT NOT NULL,company_id TEXT NOT NULL,source_type TEXT NOT NULL,source_id TEXT NOT NULL,source_version INTEGER,source_ref TEXT,split TEXT NOT NULL,status TEXT NOT NULL,instruction TEXT NOT NULL,response TEXT NOT NULL,provenance_json TEXT NOT NULL,rejection_reason TEXT,content_hash TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,FOREIGN KEY(run_id) REFERENCES finetune_dataset_runs(id));
CREATE INDEX IF NOT EXISTS idx_finetune_examples_run ON finetune_examples(run_id,status,split);
'''

def _sha(s:str)->str:return hashlib.sha256(s.encode('utf-8')).hexdigest()
def _risk_reason(text:str)->Optional[str]:
    if SECRET_RE.search(text or ''): return 'credential_or_secret_pattern'
    if EMAIL_RE.search(text or ''): return 'email_detected'
    if PHONE_RE.search(text or ''): return 'phone_detected'
    return None
def _split_for(source_id:str)->str:
    return 'validation' if int(hashlib.sha256(source_id.encode()).hexdigest()[:8],16)%10==0 else 'train'

class FineTuningDatasetManager:
    '''Prepara datasets revisables; nunca entrena un modelo.'''
    def __init__(self,db:Database,root:Path):
        self.db=db; self.root=Path(root); self.ensure_schema()
    def ensure_schema(self):
        with self.db.tx() as con: con.executescript(SCHEMA)
    def _sources(self,principal:Principal)->List[Dict[str,Any]]:
        clause,args=scope_clause(principal); out=[]
        for row in self.db.query(f"SELECT * FROM business_rules WHERE {clause} AND active=1 AND status='VALIDADO' ORDER BY updated_at DESC",args):
            d=dict(row); response=f"{d['name']}: {d['expression']}"+(f". {d['description']}" if d.get('description') else '')
            out.append({'source_type':'business_rule','source_id':d['id'],'source_version':d.get('version'),'source_ref':d.get('source_ref'),'instruction':f"¿Cuál es la regla empresarial {d['name']}?",'response':response,'provenance':{'area':d.get('area'),'source_type':d.get('source_type'),'source_ref':d.get('source_ref'),'status':d.get('status')}})
        for row in self.db.query(f"SELECT * FROM semantic_definitions WHERE {clause} AND active=1 AND status='VALIDADO' ORDER BY updated_at DESC",args):
            d=dict(row); details=[x for x in [f"tipo {d['data_type']}" if d.get('data_type') else None,f"unidad {d['unit']}" if d.get('unit') else None,d.get('description')] if x]
            response=f"{d['physical_name']} corresponde a {d['semantic_name']}"+(('. '+'. '.join(details)) if details else '')
            out.append({'source_type':'semantic_definition','source_id':d['id'],'source_version':d.get('version'),'source_ref':d.get('source_ref'),'instruction':f"¿Qué significa la columna {d['physical_name']} en la empresa?",'response':response,'provenance':{'area':d.get('area'),'source_type':d.get('source_type'),'source_ref':d.get('source_ref'),'status':d.get('status')}})
        for row in self.db.query(f"SELECT * FROM memories WHERE {clause} AND active=1 AND status='active' AND sensitivity='normal' ORDER BY importance DESC,updated_at DESC",args):
            d=dict(row); response=str(d.get('content') or '').strip()
            if not response: continue
            out.append({'source_type':'memory','source_id':d['id'],'source_version':d.get('version'),'source_ref':d.get('source_ref'),'instruction':f"Indica el conocimiento empresarial validado de categoría {d.get('category') or 'conocimiento_empresa'}.",'response':response,'provenance':{'category':d.get('category'),'source_type':d.get('source_type'),'source_ref':d.get('source_ref'),'confidence':d.get('confidence'),'status':d.get('status')}})
        return out
    def build(self,principal:Principal)->Dict[str,Any]:
        if principal.role!='admin': raise PermissionError('Se requiere rol admin')
        run_id=str(uuid.uuid4()); now=utcnow(); sources=self._sources(principal)
        self.db.execute('INSERT INTO finetune_dataset_runs(id,company_id,user_id,status,source_count,approved_count,rejected_count,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)',(run_id,principal.company_id,principal.user_id,'REVIEW',len(sources),0,0,now,now))
        seen=set(); rejected=0
        for src in sources:
            h=_sha(src['instruction']+'\n'+src['response']); reason=_risk_reason(src['instruction']+'\n'+src['response'])
            if h in seen: reason=reason or 'duplicate'
            seen.add(h); status='REJECTED' if reason else 'PENDING'; rejected+=1 if reason else 0; ex_id=str(uuid.uuid4())
            self.db.execute('INSERT INTO finetune_examples(id,run_id,company_id,source_type,source_id,source_version,source_ref,split,status,instruction,response,provenance_json,rejection_reason,content_hash,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(ex_id,run_id,principal.company_id,src['source_type'],src['source_id'],src.get('source_version'),src.get('source_ref'),_split_for(src['source_id']),status,src['instruction'],src['response'],json.dumps(src['provenance'],ensure_ascii=False),reason,h,now,now))
        self.db.execute('UPDATE finetune_dataset_runs SET rejected_count=?,updated_at=? WHERE id=?',(rejected,utcnow(),run_id))
        self.db.audit('finetune.dataset.build',principal.company_id,principal.user_id,'finetune_dataset',run_id,details={'sources':len(sources),'auto_rejected':rejected})
        return self.get_run(principal,run_id)
    @staticmethod
    def _example(row):
        d=dict(row); d['provenance']=json.loads(d.pop('provenance_json') or '{}'); return d
    def get_run(self,principal:Principal,run_id:str)->Dict[str,Any]:
        row=self.db.one('SELECT * FROM finetune_dataset_runs WHERE id=? AND company_id=?',(run_id,principal.company_id))
        if not row: raise KeyError('Dataset run no encontrado')
        d=dict(row); d['examples']=[self._example(r) for r in self.db.query('SELECT * FROM finetune_examples WHERE run_id=? AND company_id=? ORDER BY status,split,created_at',(run_id,principal.company_id))]; return d
    def list_runs(self,principal:Principal,limit:int=50)->List[Dict[str,Any]]:
        return [dict(r) for r in self.db.query('SELECT * FROM finetune_dataset_runs WHERE company_id=? ORDER BY created_at DESC LIMIT ?',(principal.company_id,max(1,min(int(limit),200))))]
    def decide(self,principal:Principal,example_id:str,approve:bool,reason:Optional[str]=None):
        if principal.role!='admin': raise PermissionError('Se requiere rol admin')
        row=self.db.one('SELECT * FROM finetune_examples WHERE id=? AND company_id=?',(example_id,principal.company_id))
        if not row: raise KeyError('Ejemplo no encontrado')
        if row['status']=='REJECTED' and row['rejection_reason'] and approve: raise ValueError('Ejemplo auto-rechazado por seguridad; corrija la fuente validada')
        status='APPROVED' if approve else 'REJECTED'; self.db.execute('UPDATE finetune_examples SET status=?,rejection_reason=?,updated_at=? WHERE id=?',(status,None if approve else (reason or 'admin_rejected'),utcnow(),example_id))
        self._refresh_counts(row['run_id']); return self._example(self.db.one('SELECT * FROM finetune_examples WHERE id=?',(example_id,)))
    def _refresh_counts(self,run_id):
        c=self.db.one("SELECT SUM(CASE WHEN status='APPROVED' THEN 1 ELSE 0 END) a,SUM(CASE WHEN status='REJECTED' THEN 1 ELSE 0 END) r FROM finetune_examples WHERE run_id=?",(run_id,))
        self.db.execute('UPDATE finetune_dataset_runs SET approved_count=?,rejected_count=?,updated_at=? WHERE id=?',(int(c['a'] or 0),int(c['r'] or 0),utcnow(),run_id))
    def approve_all_safe(self,principal:Principal,run_id:str):
        if principal.role!='admin': raise PermissionError('Se requiere rol admin')
        self.get_run(principal,run_id); self.db.execute("UPDATE finetune_examples SET status='APPROVED',updated_at=? WHERE run_id=? AND company_id=? AND status='PENDING'",(utcnow(),run_id,principal.company_id)); self._refresh_counts(run_id); return self.get_run(principal,run_id)
    def export(self,principal:Principal,run_id:str,fmt:str='jsonl')->Dict[str,Any]:
        if principal.role!='admin': raise PermissionError('Se requiere rol admin')
        if fmt not in EXPORT_FORMATS: raise ValueError('Formato no soportado')
        run=self.get_run(principal,run_id); approved=[x for x in run['examples'] if x['status']=='APPROVED']
        if not approved: raise ValueError('No hay ejemplos APPROVED para exportar')
        outdir=self.root/'workspace'/'FineTuning'; outdir.mkdir(parents=True,exist_ok=True)
        train=outdir/f'{run_id}_train.jsonl'; valid=outdir/f'{run_id}_validation.jsonl'; rejected=outdir/f'{run_id}_rejected.jsonl'
        def payload(x):
            meta={'source_type':x['source_type'],'source_id':x['source_id'],'source_version':x['source_version'],'source_ref':x['source_ref'],'provenance':x['provenance']}
            return {'instruction':x['instruction'],'input':'','output':x['response'],'metadata':meta} if fmt=='alpaca_jsonl' else {'messages':[{'role':'user','content':x['instruction']},{'role':'assistant','content':x['response']}],'metadata':meta}
        for path,split in ((train,'train'),(valid,'validation')):
            with path.open('w',encoding='utf-8',newline='\n') as f:
                for x in approved:
                    if x['split']==split: f.write(json.dumps(payload(x),ensure_ascii=False)+'\n')
        with rejected.open('w',encoding='utf-8',newline='\n') as f:
            for x in run['examples']:
                if x['status']=='REJECTED': f.write(json.dumps({'id':x['id'],'reason':x['rejection_reason'],'source_type':x['source_type'],'source_id':x['source_id']},ensure_ascii=False)+'\n')
        digest=hashlib.sha256(); [digest.update(p.read_bytes()) for p in (train,valid,rejected)]
        manifest={'run_id':run_id,'company_id':principal.company_id,'format':fmt,'train_examples':sum(x['split']=='train' for x in approved),'validation_examples':sum(x['split']=='validation' for x in approved),'rejected_examples':sum(x['status']=='REJECTED' for x in run['examples']),'sha256':digest.hexdigest(),'training_executed':False,'files':[str(train),str(valid),str(rejected)]}
        mp=outdir/f'{run_id}_manifest.json'; mp.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
        self.db.execute("UPDATE finetune_dataset_runs SET status='EXPORTED',export_format=?,export_path=?,sha256=?,updated_at=? WHERE id=?",(fmt,str(mp),manifest['sha256'],utcnow(),run_id)); self.db.audit('finetune.dataset.export',principal.company_id,principal.user_id,'finetune_dataset',run_id,details={'approved':len(approved),'training_executed':False}); return manifest
