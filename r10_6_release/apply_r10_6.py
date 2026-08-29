from __future__ import annotations
import re, shutil, sys
from datetime import datetime
from pathlib import Path

VERSION='8.5.5-r10.6-analytic-rules'

def read(p): return p.read_text(encoding='utf-8-sig')
def write(p,s): p.write_text(s,encoding='utf-8')
def once(s,old,new,label):
    if new in s: return s
    if old not in s: raise RuntimeError('No se encontro punto seguro: '+label)
    return s.replace(old,new,1)

def patch_factory(p:Path):
    s=read(p)
    if 'from .analytic_rules import AnalyticRuleEngine' not in s:
        marker='from .semantic_registry import SemanticRegistry\n'
        if marker not in s: raise RuntimeError('R10.6 requiere SemanticRegistry R10.5')
        s=s.replace(marker,marker+'from .analytic_rules import AnalyticRuleEngine\n',1)
    # constructor
    s=s.replace('governance, precedence, semantic, context, service, logger):','governance, precedence, semantic, analytics, context, service, logger):',1)
    if 'self.analytics = analytics' not in s:
        s=once(s,'        self.semantic = semantic\n','        self.semantic = semantic\n        self.analytics = analytics\n','factory analytics attr')
    if 'analytics = AnalyticRuleEngine(' not in s:
        # place after semantic regardless of surrounding construction order
        s=once(s,'    semantic = SemanticRegistry(precedence)\n','    semantic = SemanticRegistry(precedence)\n    analytics = AnalyticRuleEngine(db, governance, precedence)\n','factory analytics instantiate')
    # pass analytics to StructuredDataService if R10.4 signature currently only governance/precedence
    s=s.replace('StructuredDataService(db, llm, governance=governance, precedence=precedence)','StructuredDataService(db, llm, governance=governance, precedence=precedence, analytics=analytics)')
    # return
    s=s.replace('governance, precedence, semantic, context, service, logger)','governance, precedence, semantic, analytics, context, service, logger)',1)
    write(p,s)

def patch_structured(p:Path):
    s=read(p)
    s=s.replace('def __init__(self, db: Database, llm: Optional[LLMProvider] = None, governance=None, precedence=None):','def __init__(self, db: Database, llm: Optional[LLMProvider] = None, governance=None, precedence=None, analytics=None):',1)
    if 'self.analytics = analytics' not in s:
        s=once(s,'        self.precedence = precedence\n','        self.precedence = precedence\n        self.analytics = analytics\n','structured analytics attr')
    # Apply governed row filters immediately after work copy in query, after semantic roles are resolved.
    marker='        work = df.copy()\n'
    inject='''        work = df.copy()\n        analytic_context = self.analytics.build_context(principal, roles) if self.analytics else None\n        analytic_eval = None\n        if analytic_context:\n            from .analytic_rules import evaluate_analytic_context\n            analytic_eval = evaluate_analytic_context(work, roles, analytic_context)\n            filter_errors = [e for e in analytic_eval.get("errors", []) if e.get("stage") == "row_filter"]\n            if filter_errors:\n                return {"error":"validated_rule_failed","details":filter_errors,"source":{"type":"dataset","file":dataset["name"],"sheet":sheet,"calculation":"python/pandas"}}\n            work = analytic_eval["frame"].copy()\n'''
    if 'analytic_context = self.analytics.build_context' not in s:
        # pick query block occurrence by finding semantic_applied before marker
        pos=s.find('semantic_applied = []')
        m=s.find(marker,pos)
        if pos<0 or m<0: raise RuntimeError('structured query work marker')
        s=s[:m]+s[m:].replace(marker,inject,1)
    # After legacy profit logic and before year filter, apply metric bindings and override canonical metrics.
    year='        if plan.get("year") and "__date" in work:\n'
    metrics='''        if analytic_context:\n            from .analytic_rules import evaluate_analytic_context\n            metric_eval = evaluate_analytic_context(work, roles, {**analytic_context, "bindings":[b for b in analytic_context.get("bindings",[]) if b.get("rule_type")=="metric"]})\n            metric_errors = [e for e in metric_eval.get("errors", []) if e.get("stage") == "metric"]\n            bound_targets = {str((b.get("target") or "")).lower() for b in analytic_context.get("bindings",[]) if b.get("rule_type")=="metric"}\n            if metric_errors:\n                return {"error":"validated_rule_failed","details":metric_errors,"source":{"type":"dataset","file":dataset["name"],"sheet":sheet,"calculation":"python/pandas"}}\n            for target, vals in metric_eval.get("metrics", {}).items():\n                col={"profit":"__profit","sales":"__sales","cost":"__cost","quantity":"__quantity","freight":"__freight"}.get(target,"__metric_"+target)\n                work[col]=vals.reindex(work.index)\n'''
    if 'metric_eval = evaluate_analytic_context' not in s:
        if year not in s: raise RuntimeError('structured year marker')
        s=s.replace(year,metrics+year,1)
    # provenance
    if 'source["analytic_rules"]' not in s:
        anchor='        if rule_error:\n            source["rule_error"] = rule_error\n'
        if anchor in s:
            s=s.replace(anchor,anchor+'        if analytic_eval:\n            source["analytic_rules"]={"filters":analytic_eval.get("applied_filters",[]),"metrics":metric_eval.get("applied_metrics",[]) if analytic_context else [],"rows_input":analytic_eval.get("rows_input"),"rows_output":analytic_eval.get("rows_output")}\n',1)
    write(p,s)

def patch_bi(p:Path):
    s=read(p)
    s=s.replace('def prepare_business(df: pd.DataFrame, roles: Dict[str, Optional[str]]) -> Tuple[pd.DataFrame, Dict[str, Any], List[str]]:','def prepare_business(df: pd.DataFrame, roles: Dict[str, Optional[str]], analytic_context: Optional[Dict[str, Any]] = None) -> Tuple[pd.DataFrame, Dict[str, Any], List[str]]:',1)
    if 'analytic_eval = evaluate_analytic_context' not in s:
        old='''    work = df.copy()\n    notes: List[str] = []\n    derived: Dict[str, Any] = {'roles_bi': roles.copy()}\n'''
        new='''    work = df.copy()\n    notes: List[str] = []\n    derived: Dict[str, Any] = {'roles_bi': roles.copy()}\n    try:\n        from enterprise_ai.analytic_rules import evaluate_analytic_context, current_analytic_context\n        actx = analytic_context if analytic_context is not None else current_analytic_context()\n        analytic_eval = evaluate_analytic_context(work, roles, actx) if actx else None\n        if analytic_eval:\n            ferr=[e for e in analytic_eval.get('errors',[]) if e.get('stage')=='row_filter']\n            if ferr: raise ValueError('Regla empresarial VALIDADA no aplicable: '+str(ferr))\n            work=analytic_eval['frame'].copy()\n            derived['reglas_filtro']=analytic_eval.get('applied_filters',[])\n            derived['filas_antes_reglas']=analytic_eval.get('rows_input')\n            derived['filas_despues_reglas']=analytic_eval.get('rows_output')\n    except ImportError:\n        actx=None; analytic_eval=None\n'''
        s=once(s,old,new,'bi rule filter hook')
    # insert metric override immediately before per-quantity ratios
    anchor="    if '_cantidad' in work.columns:\n"
    block='''    if actx:\n        from enterprise_ai.analytic_rules import evaluate_analytic_context\n        mctx={**actx,'bindings':[b for b in actx.get('bindings',[]) if b.get('rule_type')=='metric']}\n        mev=evaluate_analytic_context(work,roles,mctx)\n        merr=[e for e in mev.get('errors',[]) if e.get('stage')=='metric']\n        if merr:\n            raise ValueError('Regla empresarial VALIDADA no aplicable: '+str(merr))\n        cmap={'profit':'_utilidad','sales':'_ventas','cost':'_costo','freight':'_flete','quantity':'_cantidad','commission':'_comision'}\n        for target,values in mev.get('metrics',{}).items():\n            work[cmap.get(target,'_metric_'+target)]=values.reindex(work.index)\n        derived['reglas_metricas']=mev.get('applied_metrics',[])\n'''
    if "derived['reglas_metricas']" not in s:
        if anchor not in s: raise RuntimeError('bi ratios marker')
        s=s.replace(anchor,block+anchor,1)
    write(p,s)

def patch_universal(p:Path):
    s=read(p)
    s=s.replace('def analyze_file(path: Path, prompt: str, semantic_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:','def analyze_file(path: Path, prompt: str, semantic_context: Optional[Dict[str, Any]] = None, analytic_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:',1)
    s=s.replace('bi.prepare_business(original, roles_bi)','bi.prepare_business(original, roles_bi, analytic_context)')
    write(p,s)

def patch_api(p:Path):
    s=read(p)
    if 'class RuleBindingRequest' not in s:
        marker='class SettingsRequest(BaseModel):\n'
        schema='''class RuleBindingRequest(BaseModel):\n    rule_type: str\n    target: str\n    priority: int = 100\n    scope: str = "company"\n\n\n'''
        if marker not in s: raise RuntimeError('api settings marker')
        s=s.replace(marker,schema+marker,1)
    if '/api/enterprise/rules/{rule_id}/bind' not in s:
        marker='    @router.get("/api/enterprise/datasets")\n'
        routes='''    @router.post("/api/enterprise/rules/{rule_id}/bind")\n    def bind_analytic_rule(rule_id: str, body: RuleBindingRequest, principal: Principal = Depends(admin_dependency)):\n        try:\n            return components.analytics.bind_rule(principal, rule_id, rule_type=body.rule_type, target=body.target, priority=body.priority, scope=body.scope)\n        except (ValueError, KeyError) as exc:\n            raise HTTPException(status_code=400, detail=str(exc)) from exc\n\n    @router.get("/api/enterprise/analytic-rules")\n    def list_analytic_rules(principal: Principal = Depends(principal_dependency)):\n        return {"bindings": components.analytics.applicable_bindings(principal)}\n\n'''
        if marker not in s: raise RuntimeError('api dataset marker')
        s=s.replace(marker,routes+marker,1)
    write(p,s)

def main():
    if len(sys.argv)!=3 or sys.argv[1]!='--root': raise SystemExit('Uso: python apply_r10_6.py --root C:\\ruta\\IA_Local')
    root=Path(sys.argv[2]).resolve(); scripts=root/'scripts'; pkg=scripts/'enterprise_ai'
    req=[pkg/'factory.py',pkg/'knowledge_governance.py',pkg/'precedence_engine.py',pkg/'semantic_registry.py',pkg/'structured_data.py',scripts/'bi_productivo.py',scripts/'analizador_universal.py']
    if not all(x.exists() for x in req): raise SystemExit('R10.6 requiere una instalacion R10.5 compatible')
    stamp=datetime.now().strftime('%Y%m%d_%H%M%S'); backup=root/'updates'/f'pre_r10_6_analytic_rules_{stamp}'; backup.mkdir(parents=True,exist_ok=True)
    for x in req+[pkg/'api.py',root/'VERSION.txt']:
        if x.exists(): shutil.copy2(x,backup/x.name)
    here=Path(__file__).resolve().parent
    shutil.copy2(here/'analytic_rules.py',pkg/'analytic_rules.py')
    patch_factory(pkg/'factory.py'); patch_structured(pkg/'structured_data.py'); patch_bi(scripts/'bi_productivo.py'); patch_universal(scripts/'analizador_universal.py')
    if (pkg/'api.py').exists(): patch_api(pkg/'api.py')
    (root/'VERSION.txt').write_text(VERSION+'\n',encoding='ascii')
    print('Backup:',backup); print('Version:',VERSION)

if __name__=='__main__': main()
