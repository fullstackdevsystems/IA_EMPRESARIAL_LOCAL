from __future__ import annotations
import re, shutil, sys, subprocess
from datetime import datetime
from pathlib import Path

VERSION='8.5.5-r10.5-semantic-bi'

def read(p): return p.read_text(encoding='utf-8-sig')
def write(p,s): p.write_text(s,encoding='utf-8')

def replace_once(s,old,new,label):
    if new in s: return s
    if old not in s: raise RuntimeError(f'No se encontro punto seguro: {label}')
    return s.replace(old,new,1)

def patch_factory(p:Path):
    s=read(p)
    s=replace_once(s,'from .precedence_engine import PrecedenceEngine\n','from .precedence_engine import PrecedenceEngine\nfrom .semantic_registry import SemanticRegistry\n','factory import semantic')
    # Constructor R10.4
    old='def __init__(self, cfg, db, llm, embeddings, vectors, memory, datasets, documents, governance, precedence, context, service, logger):'
    new='def __init__(self, cfg, db, llm, embeddings, vectors, memory, datasets, documents, governance, precedence, semantic, context, service, logger):'
    if old in s: s=s.replace(old,new,1)
    elif new not in s: raise RuntimeError('Constructor Components R10.4 no reconocido')
    old='        self.precedence = precedence\n        self.context = context'
    new='        self.precedence = precedence\n        self.semantic = semantic\n        self.context = context'
    s=replace_once(s,old,new,'factory self.semantic')
    old='    precedence = PrecedenceEngine(governance)\n    datasets = StructuredDataService('
    new='    precedence = PrecedenceEngine(governance)\n    semantic = SemanticRegistry(precedence)\n    datasets = StructuredDataService('
    s=replace_once(s,old,new,'factory instantiate semantic')
    old='return Components(cfg, db, llm, embeddings, vectors, memory, datasets, documents, governance, precedence, context, service, logger)'
    new='return Components(cfg, db, llm, embeddings, vectors, memory, datasets, documents, governance, precedence, semantic, context, service, logger)'
    s=replace_once(s,old,new,'factory return semantic')
    write(p,s)

def patch_bi(p:Path):
    s=read(p)
    old='def semantic_map(df: pd.DataFrame) -> Dict[str, Optional[str]]:'
    new='def semantic_map(df: pd.DataFrame, semantic_context: Optional[Dict[str, Any]] = None) -> Dict[str, Optional[str]]:'
    s=replace_once(s,old,new,'bi semantic_map signature')
    # Replace return r belonging to semantic_map, located before _coverage_ratio.
    marker='\n\ndef _coverage_ratio'
    a=s.find('def semantic_map('); b=s.find(marker,a)
    if a<0 or b<0: raise RuntimeError('semantic_map block no identificado')
    block=s[a:b]
    oldret='    return r'
    newret='''    try:\n        from enterprise_ai.semantic_registry import merge_context_roles, current_context\n        ctx = semantic_context if semantic_context is not None else current_context()\n        return merge_context_roles(r, ctx)\n    except Exception:\n        return r\n'''
    if 'merge_context_roles(r, ctx)' not in block:
        if oldret not in block: raise RuntimeError('return semantic_map no identificado')
        block=block.replace(oldret,newret,1); s=s[:a]+block+s[b:]
    write(p,s)

def patch_dynamic(p:Path):
    s=read(p)

    # R10.5 sobre R10.2+: reconstruir el resolver semantico de forma segura.
    a=s.find("def _semantic_columns(")
    b=s.find("\n\ndef _extract_top_n",a)
    if a<0 or b<0:
        raise RuntimeError("dynamic semantic block")

    semantic_block = """def _semantic_columns(df: pd.DataFrame, semantic_context: Optional[Dict[str, Any]] = None) -> Dict[str, Optional[str]]:
    # R10.2: semantic resolution is centralized and auditable.
    # R10.5: governed semantic context has precedence over BI inference.
    from semantic_layer import usable_semantic_columns

    result = usable_semantic_columns(df)

    try:
        from enterprise_ai.semantic_registry import merge_context_roles, current_context
        ctx = semantic_context if semantic_context is not None else current_context()
        return merge_context_roles(result, ctx)
    except Exception:
        return result
"""

    s=s[:a]+semantic_block.rstrip()+s[b:]

    s=s.replace(
        "def _fallback_plan(df: pd.DataFrame, prompt: str, filename: str, sheet: str) -> Dict[str, Any]:",
        "def _fallback_plan(df: pd.DataFrame, prompt: str, filename: str, sheet: str, semantic_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:"
    )
    s=s.replace(
        "    sem = _semantic_columns(df)\n",
        "    sem = _semantic_columns(df, semantic_context)\n",
        1
    )

    s=s.replace(
        "def build_dashboard_plan(df: pd.DataFrame, prompt: str, filename: str = '', sheet: str = '') -> Dict[str, Any]:",
        "def build_dashboard_plan(df: pd.DataFrame, prompt: str, filename: str = '', sheet: str = '', semantic_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:"
    )
    s=s.replace(
        "    fallback = _fallback_plan(df, prompt, filename, sheet)\n",
        "    fallback = _fallback_plan(df, prompt, filename, sheet, semantic_context)\n",
        1
    )

    s=s.replace(
        "def generate_dynamic_dashboard(output_path: Path, df: pd.DataFrame, prompt: str, filename: str, sheet: str = '') -> Dict[str, Any]:",
        "def generate_dynamic_dashboard(output_path: Path, df: pd.DataFrame, prompt: str, filename: str, sheet: str = '', semantic_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:"
    )
    s=s.replace(
        "    plan = build_dashboard_plan(df, prompt, filename, sheet)\n",
        "    plan = build_dashboard_plan(df, prompt, filename, sheet, semantic_context)\n",
        1
    )

    write(p,s)

def patch_planner(p:Path):
    s=read(p)
    s=replace_once(s,"def detect_dashboard_plan(df: pd.DataFrame, prompt: str='') -> Dict[str,Any]:","def detect_dashboard_plan(df: pd.DataFrame, prompt: str='', semantic_context: Optional[Dict[str,Any]]=None) -> Dict[str,Any]:",'planner signature')
    needle="""    customer_score=sum(bool(cols[k]) for k in ('customer_id','customer','actual','budget','previous'))"""
    inject="""    try:\n        from enterprise_ai.semantic_registry import merge_context_roles, current_context\n        ctx = semantic_context if semantic_context is not None else current_context()\n        governed = merge_context_roles({}, ctx)\n        for key in ('line','customer_id','product','customer','category','zone','seller','actual','budget','previous','period_start','period_end'):\n            if governed.get(key): cols[key] = governed[key]\n    except Exception:\n        pass\n    customer_score=sum(bool(cols[k]) for k in ('customer_id','customer','actual','budget','previous'))"""
    s=replace_once(s,needle,inject,'planner governed roles')
    write(p,s)

def patch_universal(p:Path):
    s=read(p)
    s=replace_once(s,'def analyze_file(path: Path, prompt: str) -> Dict[str, Any]:','def analyze_file(path: Path, prompt: str, semantic_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:','universal analyze signature')
    s=s.replace('    roles_bi = bi.semantic_map(original)\n','    roles_bi = bi.semantic_map(original, semantic_context)\n',1)
    s=s.replace('    dashboard_plan = dp.detect_dashboard_plan(original, prompt)\n','    dashboard_plan = dp.detect_dashboard_plan(original, prompt, semantic_context)\n',1)
    s=s.replace('dd.generate_dynamic_dashboard(html_path, original, prompt, path.name, meta.get("hoja_analizada") or "")','dd.generate_dynamic_dashboard(html_path, original, prompt, path.name, meta.get("hoja_analizada") or "", semantic_context)')
    # Generic infer_roles should also honor governed roles where compatible.
    target='        roles = infer_roles(original)\n'
    repl='''        roles = infer_roles(original)\n        try:\n            from enterprise_ai.semantic_registry import merge_context_roles\n            roles = merge_context_roles(roles, semantic_context)\n        except Exception:\n            pass\n'''
    s=s.replace(target,repl)
    write(p,s)

def patch_api(p:Path):
    s=read(p)
    # Add request schema for auditable semantic resolution.
    marker='class SettingsRequest(BaseModel):\n'
    schema='''class SemanticResolveRequest(BaseModel):\n    columns: List[str] = Field(default_factory=list)\n    inferred_roles: Dict[str, Optional[str]] = Field(default_factory=dict)\n    on_date: Optional[str] = None\n\n\n'''
    if 'class SemanticResolveRequest' not in s:
        if marker not in s: raise RuntimeError('api schema marker')
        s=s.replace(marker,schema+marker,1)
    route='''\n    @router.post("/api/enterprise/semantic/resolve")\n    def resolve_semantics(body: SemanticResolveRequest, principal: Principal = Depends(principal_dependency)):\n        return components.semantic.resolve(principal, body.columns, body.inferred_roles, on_date=body.on_date)\n\n'''
    if '/api/enterprise/semantic/resolve' not in s:
        marker='    @router.get("/api/enterprise/datasets")\n'
        if marker not in s: raise RuntimeError('api route marker')
        s=s.replace(marker,route+marker,1)
    write(p,s)

def main():
    if len(sys.argv)!=3 or sys.argv[1]!='--root': raise SystemExit('Uso: python apply_r10_5.py --root C:\\ruta\\IA_Local')
    root=Path(sys.argv[2]).resolve(); scripts=root/'scripts'; pkg=scripts/'enterprise_ai'
    req=[pkg/'factory.py',pkg/'precedence_engine.py',pkg/'knowledge_governance.py',scripts/'bi_productivo.py',scripts/'dashboard_dynamic.py',scripts/'dashboard_planner.py',scripts/'analizador_universal.py']
    if not all(x.exists() for x in req): raise SystemExit('R10.5 requiere una instalacion R10.4 compatible')
    stamp=datetime.now().strftime('%Y%m%d_%H%M%S'); backup=root/'updates'/f'pre_r10_5_semantic_bi_{stamp}'; backup.mkdir(parents=True,exist_ok=True)
    for x in req+[pkg/'api.py',root/'VERSION.txt']:
        if x.exists(): shutil.copy2(x,backup/x.name)
    here=Path(__file__).resolve().parent
    shutil.copy2(here/'semantic_registry.py',pkg/'semantic_registry.py')
    patch_factory(pkg/'factory.py'); patch_bi(scripts/'bi_productivo.py'); patch_dynamic(scripts/'dashboard_dynamic.py'); patch_planner(scripts/'dashboard_planner.py'); patch_universal(scripts/'analizador_universal.py')
    if (pkg/'api.py').exists(): patch_api(pkg/'api.py')
    (root/'VERSION.txt').write_text(VERSION+'\n',encoding='ascii')
    print('Backup:',backup); print('Version:',VERSION)

if __name__=='__main__': main()

