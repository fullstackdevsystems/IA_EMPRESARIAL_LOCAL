from __future__ import annotations
import argparse, re, shutil
from pathlib import Path
from datetime import datetime

HERE = Path(__file__).resolve().parent

def backup(path: Path, root: Path, bdir: Path):
    if path.exists():
        dst=bdir/path.relative_to(root); dst.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(path,dst)

def patch_factory(path: Path):
    s=path.read_text(encoding='utf-8')
    if 'from .feedback import FeedbackManager' not in s:
        anchor='from .context_engine import ContextEngine\n'
        if anchor not in s: raise RuntimeError('factory import anchor no encontrado')
        s=s.replace(anchor,anchor+'from .feedback import FeedbackManager\n',1)

    # Inserta feedback en la firma Components conservando cualquier componente R10.x adicional.
    m=re.search(r'def __init__\(self, ([^\n]+)\):',s)
    if not m: raise RuntimeError('factory Components signature no encontrada')
    args=[x.strip() for x in m.group(1).split(',')]
    if 'memory' not in args: raise RuntimeError('factory memory arg no encontrado')
    if 'feedback' not in args:
        args.insert(args.index('memory')+1,'feedback')
        s=s[:m.start()]+'def __init__(self, '+', '.join(args)+'):'+s[m.end():]
    if 'self.feedback = feedback' not in s:
        anchor2='        self.memory = memory\n'
        if anchor2 not in s: raise RuntimeError('factory self.memory no encontrado')
        s=s.replace(anchor2,anchor2+'        self.feedback = feedback\n',1)

    # Governance debe existir antes de crear FeedbackManager para que las correcciones
    # de reglas/semantica queden PROPUESTAS en la capa gobernada.
    if 'feedback = FeedbackManager' not in s:
        if '    governance = KnowledgeGovernance(db)\n' in s:
            anchor3='    governance = KnowledgeGovernance(db)\n'
            s=s.replace(anchor3,anchor3+'    feedback = FeedbackManager(db, memory, governance)\n',1)
        else:
            # Compatibilidad hacia atrás: sin governance solo permite memoria pendiente.
            anchor3='    memory = MemoryManager(db, embeddings, vectors)\n'
            if anchor3 not in s: raise RuntimeError('factory memory wiring no encontrado')
            s=s.replace(anchor3,anchor3+'    feedback = FeedbackManager(db, memory, None)\n',1)

    # Inserta feedback en el constructor final sin alterar componentes existentes.
    m=re.search(r'    return Components\(([^\n]+)\)',s)
    if not m: raise RuntimeError('factory return Components no encontrado')
    ret=[x.strip() for x in m.group(1).split(',')]
    if 'memory' not in ret: raise RuntimeError('factory return memory no encontrado')
    if 'feedback' not in ret:
        ret.insert(ret.index('memory')+1,'feedback')
        s=s[:m.start()]+'    return Components('+', '.join(ret)+')'+s[m.end():]
    path.write_text(s,encoding='utf-8')

def patch_api(path: Path):
    s=path.read_text(encoding='utf-8')
    if 'class FeedbackRequest(BaseModel):' not in s:
        anchor='class SettingsRequest(BaseModel):\n'
        if anchor not in s: raise RuntimeError('api SettingsRequest anchor no encontrado')
        block='''class FeedbackRequest(BaseModel):\n    feedback_type: str\n    target_type: Optional[str] = None\n    target_ref: Optional[str] = None\n    area: Optional[str] = None\n    original_text: Optional[str] = None\n    correction_text: Optional[str] = None\n    proposal_type: str = "auto"\n    proposal_name: Optional[str] = None\n    physical_name: Optional[str] = None\n    semantic_name: Optional[str] = None\n    valid_from: Optional[str] = None\n    valid_to: Optional[str] = None\n    scope: str = "company"\n    source_context: Dict[str, Any] = Field(default_factory=dict)\n\n\nclass FeedbackDecisionRequest(BaseModel):\n    replace_conflicts: bool = False\n\n\n'''
        s=s.replace(anchor,block+anchor,1)
    if '/api/enterprise/feedback' not in s:
        marker='    @router.get("/api/enterprise/settings")\n'
        if marker not in s: raise RuntimeError('api settings endpoint anchor no encontrado')
        endpoints='''    @router.get("/api/enterprise/feedback")\n    def list_feedback(limit: int = 100, principal: Principal = Depends(principal_dependency)):\n        return {"feedback": components.feedback.list(principal, limit=limit)}\n\n    @router.post("/api/enterprise/feedback")\n    def submit_feedback(body: FeedbackRequest, principal: Principal = Depends(principal_dependency)):\n        try:\n            return components.feedback.submit(principal, **body.model_dump())\n        except (ValueError, RuntimeError) as exc:\n            raise HTTPException(status_code=400, detail=str(exc)) from exc\n\n    @router.post("/api/enterprise/feedback/{feedback_id}/validate")\n    def validate_feedback(feedback_id: str, body: FeedbackDecisionRequest, principal: Principal = Depends(principal_dependency)):\n        try:\n            return components.feedback.validate_proposal(principal, feedback_id, replace_conflicts=body.replace_conflicts)\n        except KeyError as exc:\n            raise HTTPException(status_code=404, detail=str(exc)) from exc\n        except ValueError as exc:\n            raise HTTPException(status_code=409, detail=str(exc)) from exc\n\n    @router.post("/api/enterprise/feedback/{feedback_id}/reject")\n    def reject_feedback(feedback_id: str, principal: Principal = Depends(principal_dependency)):\n        try:\n            return components.feedback.reject_proposal(principal, feedback_id)\n        except KeyError as exc:\n            raise HTTPException(status_code=404, detail=str(exc)) from exc\n        except ValueError as exc:\n            raise HTTPException(status_code=409, detail=str(exc)) from exc\n\n    @router.get("/api/enterprise/feedback/{feedback_id}/provenance")\n    def feedback_provenance(feedback_id: str, principal: Principal = Depends(principal_dependency)):\n        try:\n            return components.feedback.provenance(principal, feedback_id)\n        except KeyError as exc:\n            raise HTTPException(status_code=404, detail=str(exc)) from exc\n\n'''
        s=s.replace(marker,endpoints+marker,1)
    # Assistant UI: inject controls via helper functions, minimally invasive.
    if 'function feedbackButtons' not in s:
        anchor_js='function sourceHtml(d){'
        if anchor_js not in s: raise RuntimeError('api sourceHtml JS anchor no encontrado')
        helper=r'''function feedbackButtons(doneEvent,answer){const box=document.createElement('div');box.className='status';box.style.marginTop='8px';const ok=document.createElement('button');ok.className='btn ok';ok.textContent='👍 Correcto';ok.style.padding='5px 9px';const bad=document.createElement('button');bad.className='btn danger';bad.textContent='👎 Requiere corrección';bad.style.padding='5px 9px';box.append(ok,bad);ok.onclick=async()=>{ok.disabled=bad.disabled=true;await fetch('/api/enterprise/feedback',{method:'POST',headers:{'Content-Type':'application/json','Authorization':'Bearer '+token},body:JSON.stringify({feedback_type:'CORRECTO',target_type:'chat',target_ref:doneEvent.request_id||null,original_text:answer,source_context:{sources:doneEvent.sources||[]}})});box.textContent='Feedback registrado.'};bad.onclick=async()=>{const correction=prompt('Indica la corrección. Se guardará como PROPUESTA, no como verdad validada:');if(!correction)return;const r=await fetch('/api/enterprise/feedback',{method:'POST',headers:{'Content-Type':'application/json','Authorization':'Bearer '+token},body:JSON.stringify({feedback_type:'REQUIERE_CORRECCION',target_type:'chat',target_ref:doneEvent.request_id||null,original_text:answer,correction_text:correction,proposal_type:'auto',source_context:{sources:doneEvent.sources||[]}})});let d={};try{d=await r.json()}catch{}if(!r.ok){alert(d.detail||'No se pudo registrar la corrección');return}box.innerHTML='Corrección registrada como <b>'+escHtml(d.proposal_type||'propuesta')+'</b> / '+escHtml(d.proposal_status||'PROPUESTO')+'. ';if(d.proposal_object_id){const save=document.createElement('button');save.className='btn ok';save.textContent='Guardar / Validar';save.style.padding='5px 9px';const reject=document.createElement('button');reject.className='btn danger';reject.textContent='Rechazar';reject.style.padding='5px 9px';box.append(save,reject);save.onclick=async()=>{const vr=await fetch('/api/enterprise/feedback/'+encodeURIComponent(d.id)+'/validate',{method:'POST',headers:{'Content-Type':'application/json','Authorization':'Bearer '+token},body:JSON.stringify({replace_conflicts:false})});let vd={};try{vd=await vr.json()}catch{}if(vr.ok)box.textContent='Propuesta VALIDADA y guardada.';else alert(vd.detail||'No se pudo validar; puede existir un conflicto.')};reject.onclick=async()=>{const rr=await fetch('/api/enterprise/feedback/'+encodeURIComponent(d.id)+'/reject',{method:'POST',headers:{'Authorization':'Bearer '+token}});if(rr.ok)box.textContent='Propuesta rechazada.'}}};return box}\n'''
        s=s.replace(anchor_js,helper+anchor_js,1)
    # attach buttons to done bubble
    target="src.innerHTML=sourceHtml(ev);bubble.appendChild(src);hist.push({role:'user',content:m},{role:'assistant',content:answer});"
    if target in s and 'bubble.appendChild(feedbackButtons(ev,answer))' not in s:
        s=s.replace(target,"src.innerHTML=sourceHtml(ev);bubble.appendChild(src);bubble.appendChild(feedbackButtons(ev,answer));hist.push({role:'user',content:m},{role:'assistant',content:answer});",1)
    path.write_text(s,encoding='utf-8')

def main(root: Path):
    root=root.resolve(); ent=root/'scripts'/'enterprise_ai'
    if not ent.exists(): raise RuntimeError('No existe enterprise_ai')
    bdir=root/'updates'/('pre_r10_8_feedback_'+datetime.now().strftime('%Y%m%d_%H%M%S')); bdir.mkdir(parents=True,exist_ok=True)
    for p in [ent/'factory.py',ent/'api.py',root/'VERSION.txt']: backup(p,root,bdir)
    shutil.copy2(HERE/'feedback.py',ent/'feedback.py')
    patch_factory(ent/'factory.py'); patch_api(ent/'api.py')
    (root/'VERSION.txt').write_text('8.5.5-r10.8-feedback-learning\n',encoding='utf-8')
    print(f'Backup: {bdir}'); print('R10.8 patch OK')

if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('--root',required=True); a=ap.parse_args(); main(Path(a.root))
