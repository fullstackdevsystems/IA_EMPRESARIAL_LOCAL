from __future__ import annotations
import argparse, re, shutil
from datetime import datetime
from pathlib import Path
HERE=Path(__file__).resolve().parent

def backup(path,root,bdir):
    if path.exists():
        dst=bdir/path.relative_to(root); dst.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(path,dst)

def patch_api(path: Path):
    s=path.read_text(encoding='utf-8')
    if 'from .admin_console import UNIFIED_ADMIN_HTML' not in s:
        anchor='from .security import Principal, ensure_secret, safe_component, verify_token\n'
        if anchor not in s: raise RuntimeError('api import anchor no encontrado')
        s=s.replace(anchor,anchor+'from .admin_console import UNIFIED_ADMIN_HTML\n',1)
    s=s.replace('        return ADMIN_HTML\n','        return UNIFIED_ADMIN_HTML\n',1)
    # Request models, deliberately additive and generic.
    model_anchor='class SettingsRequest(BaseModel):\n'
    if 'class GovernanceValidateRequest' not in s:
        if model_anchor not in s: raise RuntimeError('SettingsRequest anchor no encontrado')
        models='''class GovernanceValidateRequest(BaseModel):
    replace_conflicts: bool = False

class BusinessRuleCreateRequest(BaseModel):
    name: str
    expression: str
    area: Optional[str] = None
    description: Optional[str] = None
    scope: str = "company"
    valid_from: Optional[str] = None
    valid_to: Optional[str] = None

class SemanticDefinitionCreateRequest(BaseModel):
    physical_name: str
    semantic_name: str
    data_type: Optional[str] = None
    unit: Optional[str] = None
    area: Optional[str] = None
    description: Optional[str] = None
    scope: str = "company"
    valid_from: Optional[str] = None
    valid_to: Optional[str] = None

class AnalyticBindRequest(BaseModel):
    rule_type: str
    target: str
    priority: int = 100
    scope: str = "company"

'''
        s=s.replace(model_anchor,models+model_anchor,1)
    marker='    @router.get("/api/enterprise/settings")\n'
    if '/api/enterprise/admin/overview' not in s:
        if marker not in s: raise RuntimeError('api settings marker no encontrado')
        endpoints=r'''    @router.get("/api/enterprise/admin/overview")
    def admin_overview(principal: Principal = Depends(principal_dependency)):
        rules = components.governance.list_rules(principal, include_inactive=True) if hasattr(components, "governance") else []
        sem = components.governance.list_semantic_definitions(principal, include_inactive=True) if hasattr(components, "governance") else []
        feedback = components.feedback.list(principal, limit=500) if hasattr(components, "feedback") else []
        traces = components.traceability.list(principal, limit=500) if hasattr(components, "traceability") else []
        memories = components.memory.list(principal, include_inactive=True)
        docs = components.documents.list(principal)
        datasets = components.datasets.list(principal)
        statuses=[]
        for typ, rows in (("Regla", rules),("Definición", sem)):
            counts={}
            for row in rows: counts[row.get("status") or "N/D"]=counts.get(row.get("status") or "N/D",0)+1
            statuses.extend({"type":typ,"status":k,"count":v} for k,v in sorted(counts.items()))
        conflicts=0
        if hasattr(components,"governance"):
            for row in rules:
                if row.get("status") == "PROPUESTO": conflicts += len(components.governance.detect_rule_conflicts(principal,row["id"]))
            for row in sem:
                if row.get("status") == "PROPUESTO": conflicts += len(components.governance.detect_semantic_conflicts(principal,row["id"]))
        return {"counts":{"memories":len(memories),"documents":len(docs),"datasets":len(datasets),"rules":len(rules),"semantic_definitions":len(sem),"feedback_pending":sum(1 for x in feedback if x.get("proposal_status")=="PROPUESTO"),"traces":len(traces),"conflicts":conflicts},"statuses":statuses}

    @router.get("/api/enterprise/business-rules")
    def list_business_rules(status: Optional[str]=None, include_inactive: bool=False, principal: Principal=Depends(principal_dependency)):
        return {"items": components.governance.list_rules(principal,status=status,include_inactive=include_inactive)}

    @router.post("/api/enterprise/business-rules")
    def propose_business_rule(body: BusinessRuleCreateRequest, principal: Principal=Depends(principal_dependency)):
        return components.governance.propose_rule(principal,name=body.name,expression=body.expression,area=body.area,description=body.description,scope=body.scope,valid_from=body.valid_from,valid_to=body.valid_to,source_type="admin_console")

    @router.post("/api/enterprise/business-rules/{rule_id}/validate")
    def validate_business_rule(rule_id: str, body: GovernanceValidateRequest, principal: Principal=Depends(admin_dependency)):
        return components.governance.validate_rule(principal,rule_id,replace_conflicts=body.replace_conflicts)

    @router.post("/api/enterprise/business-rules/{rule_id}/reject")
    def reject_business_rule(rule_id: str, principal: Principal=Depends(admin_dependency)):
        return components.governance.reject_rule(principal,rule_id)

    @router.post("/api/enterprise/business-rules/{rule_id}/obsolete")
    def obsolete_business_rule(rule_id: str, principal: Principal=Depends(admin_dependency)):
        return components.governance.obsolete_rule(principal,rule_id)

    @router.get("/api/enterprise/semantic-definitions")
    def list_semantic_definitions(status: Optional[str]=None, include_inactive: bool=False, principal: Principal=Depends(principal_dependency)):
        return {"items": components.governance.list_semantic_definitions(principal,status=status,include_inactive=include_inactive)}

    @router.post("/api/enterprise/semantic-definitions")
    def propose_semantic_definition(body: SemanticDefinitionCreateRequest, principal: Principal=Depends(principal_dependency)):
        return components.governance.propose_semantic_definition(principal,physical_name=body.physical_name,semantic_name=body.semantic_name,data_type=body.data_type,unit=body.unit,area=body.area,description=body.description,scope=body.scope,valid_from=body.valid_from,valid_to=body.valid_to,source_type="admin_console")

    @router.post("/api/enterprise/semantic-definitions/{item_id}/validate")
    def validate_semantic_definition(item_id: str, body: GovernanceValidateRequest, principal: Principal=Depends(admin_dependency)):
        return components.governance.validate_semantic_definition(principal,item_id,replace_conflicts=body.replace_conflicts)

    @router.post("/api/enterprise/semantic-definitions/{item_id}/reject")
    def reject_semantic_definition(item_id: str, principal: Principal=Depends(admin_dependency)):
        return components.governance.reject_semantic_definition(principal,item_id)

    @router.get("/api/enterprise/analytic-rules")
    def list_analytic_rules(principal: Principal=Depends(principal_dependency)):
        if not hasattr(components,"analytic_rules"): return {"items":[]}
        return {"items": components.analytic_rules.applicable_bindings(principal)}

    @router.post("/api/enterprise/rules/{rule_id}/bind")
    def bind_analytic_rule(rule_id: str, body: AnalyticBindRequest, principal: Principal=Depends(admin_dependency)):
        return components.analytic_rules.bind_rule(principal,rule_id,rule_type=body.rule_type,target=body.target,priority=body.priority,scope=body.scope)

    @router.get("/api/enterprise/knowledge/{object_type}/{object_id}/history")
    def knowledge_history(object_type: str, object_id: str, principal: Principal=Depends(principal_dependency)):
        if object_type not in {"business_rule","semantic_definition"}: raise HTTPException(status_code=400,detail="object_type no válido")
        try: return components.governance.provenance(principal,object_type,object_id)
        except KeyError as exc: raise HTTPException(status_code=404,detail=str(exc)) from exc

'''
        s=s.replace(marker,endpoints+marker,1)
    path.write_text(s,encoding='utf-8')

def main(root: Path):
    root=root.resolve(); ent=root/'scripts'/'enterprise_ai'; api=ent/'api.py'
    if not api.exists(): raise RuntimeError('No existe enterprise_ai/api.py')
    bdir=root/'updates'/('pre_r10_10_admin_'+datetime.now().strftime('%Y%m%d_%H%M%S')); bdir.mkdir(parents=True,exist_ok=True)
    for p in [api,ent/'admin_console.py',root/'VERSION.txt']: backup(p,root,bdir)
    shutil.copy2(HERE/'admin_console.py',ent/'admin_console.py'); patch_api(api)
    (root/'VERSION.txt').write_text('8.5.5-r10.10-unified-admin\n',encoding='utf-8')
    print(f'Backup: {bdir}'); print('R10.10 patch OK')
if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('--root',required=True); a=ap.parse_args(); main(Path(a.root))
