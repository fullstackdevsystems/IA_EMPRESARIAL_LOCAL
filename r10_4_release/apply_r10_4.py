from __future__ import annotations

import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

VERSION='8.5.5-r10.4-precedence'


def must_replace(text, old, new, label):
    if old in text:
        return text.replace(old,new,1)
    if new in text:
        return text
    raise RuntimeError(f'No se encontro punto seguro de parcheo: {label}')


def patch_factory(path: Path):
    s=path.read_text(encoding='utf-8-sig')
    if 'from .knowledge_governance import KnowledgeGovernance' not in s:
        s=must_replace(s,'from .memory import MemoryManager','from .memory import MemoryManager\nfrom .knowledge_governance import KnowledgeGovernance','factory import governance')
    if 'from .precedence_engine import PrecedenceEngine' not in s:
        s=must_replace(s,'from .knowledge_governance import KnowledgeGovernance','from .knowledge_governance import KnowledgeGovernance\nfrom .precedence_engine import PrecedenceEngine','factory import precedence')

    # Normalize Components constructor for either pre-R10.3 or R10.3 installations.
    sig_re=r'def __init__\(self, cfg, db, llm, embeddings, vectors, memory, datasets, documents,(?: governance,)?(?: precedence,)? context, service, logger\):'
    s,n=re.subn(sig_re,'def __init__(self, cfg, db, llm, embeddings, vectors, memory, datasets, documents, governance, precedence, context, service, logger):',s,count=1)
    if n!=1 and 'def __init__(self, cfg, db, llm, embeddings, vectors, memory, datasets, documents, governance, precedence, context, service, logger):' not in s:
        raise RuntimeError('Firma Components inesperada')
    if 'self.governance = governance' not in s:
        s=must_replace(s,'        self.documents = documents','        self.documents = documents\n        self.governance = governance','factory self governance')
    if 'self.precedence = precedence' not in s:
        s=must_replace(s,'        self.governance = governance','        self.governance = governance\n        self.precedence = precedence','factory self precedence')

    # Replace construction block regardless of R10.3 ordering.
    pattern=re.compile(r'    memory = MemoryManager\(db, embeddings, vectors\)\n(?:    governance = KnowledgeGovernance\(db\)\n)?    datasets = StructuredDataService\(db, llm\)\n    documents = DocumentService\(cfg, db, embeddings, vectors, datasets\)\n(?:    governance = KnowledgeGovernance\(db\)\n)?    context = ContextEngine\(memory, documents, datasets, cfg\.section\("retrieval"\)\)')
    replacement=(
        '    memory = MemoryManager(db, embeddings, vectors)\n'
        '    governance = KnowledgeGovernance(db)\n'
        '    precedence = PrecedenceEngine(governance)\n'
        '    datasets = StructuredDataService(db, llm, governance=governance, precedence=precedence)\n'
        '    documents = DocumentService(cfg, db, embeddings, vectors, datasets)\n'
        '    context = ContextEngine(memory, documents, datasets, cfg.section("retrieval"), governance=governance, precedence=precedence)'
    )
    s,n=pattern.subn(replacement,s,count=1)
    if n!=1 and 'precedence = PrecedenceEngine(governance)' not in s:
        raise RuntimeError('Bloque build_components inesperado')

    ret_re=r'    return Components\(cfg, db, llm, embeddings, vectors, memory, datasets, documents,(?: governance,)?(?: precedence,)? context, service, logger\)'
    s,n=re.subn(ret_re,'    return Components(cfg, db, llm, embeddings, vectors, memory, datasets, documents, governance, precedence, context, service, logger)',s,count=1)
    if n!=1 and 'documents, governance, precedence, context, service, logger)' not in s:
        raise RuntimeError('Return Components inesperado')
    path.write_text(s,encoding='utf-8')


def patch_structured(path: Path):
    s=path.read_text(encoding='utf-8-sig')
    old='    def __init__(self, db: Database, llm: Optional[LLMProvider] = None):\n        self.db = db\n        self.llm = llm'
    new='    def __init__(self, db: Database, llm: Optional[LLMProvider] = None, governance=None, precedence=None):\n        self.db = db\n        self.llm = llm\n        self.governance = governance\n        self.precedence = precedence'
    s=must_replace(s,old,new,'StructuredDataService.__init__')

    old='        roles = roles or inferred_roles\n        file_hash = file_hash or hash_file(path)'
    new='        roles = roles or inferred_roles\n        if self.precedence:\n            roles, _semantic_applied = self.precedence.semantic_overrides(principal, columns, roles)\n        file_hash = file_hash or hash_file(path)'
    s=must_replace(s,old,new,'register semantic precedence')

    qpat=re.compile(r'(?m)^(?P<i>\s*)roles = infer_roles\(list\(map\(str, df\.columns\)\)\)\s*\n(?P=i)work = df\.copy\(\)')
    qrepl='        roles = infer_roles(list(map(str, df.columns)))\n        semantic_applied = []\n        if self.precedence:\n            roles, semantic_applied = self.precedence.semantic_overrides(principal, list(map(str, df.columns)), roles)\n        work = df.copy()'
    if 'semantic_applied = []' not in s:
        s,n=qpat.subn(qrepl,s,count=1)
        if n!=1: raise RuntimeError('No se encontro punto seguro de parcheo: query semantic precedence')

    start='        rule_used = None\n        if plan.get("metric") == "profit":'
    end='        if plan.get("year") and "__date" in work:'
    if start in s:
        a=s.index(start); b=s.index(end,a)
        replacement='''        rule_used = None\n        rule_error = None\n        if plan.get("metric") == "profit":\n            validated_rule = self.precedence.rule_for_metric(principal, "profit", question=prompt) if self.precedence else None\n            if validated_rule:\n                try:\n                    work["__profit"] = self.precedence.evaluate_rule(work, roles, validated_rule)\n                    rule_used = {\n                        "id": validated_rule.get("id"), "name": validated_rule.get("name"),\n                        "version": validated_rule.get("version"), "expression": validated_rule.get("expression"),\n                        "source_type": validated_rule.get("source_type"), "source_ref": validated_rule.get("source_ref"),\n                        "precedence": "validated_business_rule",\n                    }\n                except ValueError as exc:\n                    # Una regla VALIDADA tiene precedencia: si no puede ejecutarse con\n                    # columnas validadas, no degradamos silenciosamente a una fórmula inferida.\n                    rule_error = str(exc)\n            else:\n                for memory in memories or []:\n                    c = norm(memory.get("content"))\n                    if "utilidad" in c and "venta" in c and ("compra" in c or "costo" in c):\n                        rule_used = memory.get("content")\n                        break\n                if "__sales" in work and "__cost" in work:\n                    profit = work["__sales"] - work["__cost"]\n                    if roles.get("freight"):\n                        profit = profit - pd.to_numeric(work[roles["freight"]], errors="coerce").fillna(0)\n                    work["__profit"] = profit\n'''
        s=s[:a]+replacement+s[b:]
    elif 'validated_rule = self.precedence.rule_for_metric' not in s:
        raise RuntimeError('Bloque profit inesperado')

    # Enrich source provenance after source dict closes, before calculation branches.
    needle='''        source = {\n            "type": "dataset",\n            "file": dataset["name"],\n            "sheet": sheet,\n            "rows_used": int(len(work)),\n            "filters": plan.get("filters", []),\n            "year": plan.get("year"),\n            "calculation": "python/pandas",\n        }'''
    repl=needle+'''\n        if semantic_applied:\n            source["semantic_definitions"] = semantic_applied\n        if rule_used:\n            source["business_rule"] = rule_used\n        if rule_error:\n            source["rule_error"] = rule_error'''
    s=must_replace(s,needle,repl,'structured provenance')
    path.write_text(s,encoding='utf-8')


def patch_context(path: Path):
    s=path.read_text(encoding='utf-8-sig')
    old='    def __init__(self, memory: MemoryManager, documents: DocumentService, structured: StructuredDataService, retrieval_cfg: Dict[str, Any]):\n        self.memory = memory\n        self.documents = documents\n        self.structured = structured\n        self.cfg = retrieval_cfg'
    new='    def __init__(self, memory: MemoryManager, documents: DocumentService, structured: StructuredDataService, retrieval_cfg: Dict[str, Any], governance=None, precedence=None):\n        self.memory = memory\n        self.documents = documents\n        self.structured = structured\n        self.cfg = retrieval_cfg\n        self.governance = governance\n        self.precedence = precedence'
    s=must_replace(s,old,new,'ContextEngine.__init__')

    needle='''        sources: List[Dict[str, Any]] = []\n        blocks: List[str] = []\n        if structured:'''
    repl='''        sources: List[Dict[str, Any]] = []\n        blocks: List[str] = []\n        governed = self.precedence.knowledge_context(principal, question) if self.precedence else {"rules": [], "semantic_definitions": [], "precedence": []}\n        if governed.get("rules"):\n            lines = ["REGLAS EMPRESARIALES VALIDADAS (máxima autoridad empresarial aplicable):"]\n            for index, rule in enumerate(governed["rules"], 1):\n                lines.append(f"[R{index}] {rule.get('name')} v{rule.get('version')}: {rule.get('expression')} (area={rule.get('area') or 'N/D'})")\n                sources.append({"type":"business_rule","rule_id":rule.get("id"),"name":rule.get("name"),"version":rule.get("version"),"source_type":rule.get("source_type"),"source_ref":rule.get("source_ref")})\n            blocks.append("\\n".join(lines))\n        if governed.get("semantic_definitions"):\n            lines = ["DEFINICIONES SEMANTICAS VALIDADAS:"]\n            for index, item in enumerate(governed["semantic_definitions"], 1):\n                lines.append(f"[S{index}] {item.get('physical_name')} -> {item.get('semantic_name')} (rol={item.get('role')})")\n                sources.append({"type":"semantic_definition","definition_id":item.get("definition_id"),"physical_name":item.get("physical_name"),"semantic_name":item.get("semantic_name")})\n            blocks.append("\\n".join(lines))\n        if structured:'''
    s=must_replace(s,needle,repl,'governed context')

    old='''            "Eres el asistente de IA Empresarial Local. Prioridad: 1) politicas del sistema, 2) permisos, "\n            "3) datos estructurados calculados, 4) documentos recuperados, 5) memoria permanente, "\n            "6) conversacion reciente, 7) conocimiento general. Nunca inventes cifras, clientes, proveedores, "'''
    new='''            "Eres el asistente de IA Empresarial Local. Prioridad: 1) politicas del sistema, 2) permisos, "\n            "3) reglas empresariales VALIDADAS vigentes, 4) definiciones semanticas VALIDADAS, "\n            "5) datos estructurados calculados deterministicamente, 6) documentos oficiales recuperados, "\n            "7) memoria confirmada, 8) conversacion reciente/inferencia, 9) conocimiento general. Nunca inventes cifras, clientes, proveedores, "'''
    s=must_replace(s,old,new,'system precedence prompt')
    path.write_text(s,encoding='utf-8')


def main():
    if len(sys.argv)!=3 or sys.argv[1] != '--root':
        raise SystemExit('Uso: python apply_r10_4.py --root C:\\ruta\\IA_Local')
    root=Path(sys.argv[2]).resolve()
    pkg=root/'scripts'/'enterprise_ai'
    required=[pkg/'factory.py',pkg/'structured_data.py',pkg/'context_engine.py',pkg/'database.py',pkg/'security.py']
    if not all(p.exists() for p in required):
        raise SystemExit('La ruta no parece una instalacion IA_Local compatible')
    stamp=datetime.now().strftime('%Y%m%d_%H%M%S')
    backup=root/'updates'/f'pre_r10_4_precedence_{stamp}'
    backup.mkdir(parents=True,exist_ok=True)
    for name in ('factory.py','structured_data.py','context_engine.py','knowledge_governance.py','precedence_engine.py'):
        src=pkg/name
        if src.exists(): shutil.copy2(src,backup/name)
    v=root/'VERSION.txt'
    if v.exists(): shutil.copy2(v,backup/'VERSION.txt')

    here=Path(__file__).resolve().parent
    shutil.copy2(here/'knowledge_governance.py',pkg/'knowledge_governance.py')
    shutil.copy2(here/'precedence_engine.py',pkg/'precedence_engine.py')
    patch_factory(pkg/'factory.py')
    patch_structured(pkg/'structured_data.py')
    patch_context(pkg/'context_engine.py')
    v.write_text(VERSION+'\n',encoding='ascii')
    print(f'Backup: {backup}')
    print(f'Version: {VERSION}')

if __name__=='__main__': main()
