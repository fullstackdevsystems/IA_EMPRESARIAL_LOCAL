from __future__ import annotations
import argparse, shutil, re
from pathlib import Path
from datetime import datetime

HERE=Path(__file__).resolve().parent

def backup(path: Path, root: Path, bdir: Path):
    if path.exists():
        rel=path.relative_to(root); dst=bdir/rel; dst.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(path,dst)

def patch_factory(path: Path):
    s=path.read_text(encoding='utf-8')
    if 'AdvancedRetrievalEngine' not in s:
        anchor='from .context_engine import ContextEngine\n'
        if anchor not in s: raise RuntimeError('factory: import anchor no encontrado')
        s=s.replace(anchor, anchor+'from .advanced_retrieval import AdvancedRetrievalEngine\n',1)
    old='context = ContextEngine(memory, documents, datasets, cfg.section("retrieval"))'
    if old in s:
        s=s.replace(old,'advanced_retrieval = AdvancedRetrievalEngine(memory, documents, governance if \'governance\' in locals() else None, cfg.section("retrieval"))\n    context = ContextEngine(memory, documents, datasets, cfg.section("retrieval"), advanced_retrieval=advanced_retrieval)',1)
    elif 'advanced_retrieval=advanced_retrieval' not in s:
        raise RuntimeError('factory: wiring ContextEngine no reconocido')
    path.write_text(s,encoding='utf-8')

def patch_context(path: Path):
    s=path.read_text(encoding='utf-8')
    # Constructor compatible hacia atras.
    pat=r'def __init__\(self, memory: MemoryManager, documents: DocumentService, structured: StructuredDataService, retrieval_cfg: Dict\[str, Any\]\):\n\s+self\.memory = memory\n\s+self\.documents = documents\n\s+self\.structured = structured\n\s+self\.cfg = retrieval_cfg'
    repl='def __init__(self, memory: MemoryManager, documents: DocumentService, structured: StructuredDataService, retrieval_cfg: Dict[str, Any], advanced_retrieval=None):\n        self.memory = memory\n        self.documents = documents\n        self.structured = structured\n        self.cfg = retrieval_cfg\n        self.advanced_retrieval = advanced_retrieval'
    if 'self.advanced_retrieval' not in s:
        ns,n=re.subn(pat,repl,s,count=1)
        if n!=1: raise RuntimeError('context: constructor no reconocido')
        s=ns

    # Sustituye solo la recuperación memoria/documentos original, manteniendo structured.
    start='''        started = time.perf_counter()\n        memories = self.memory.search(\n            principal,\n            question,\n            int(self.cfg.get("max_memories", 6)),\n            float(self.cfg.get("memory_min_score", 0.20)),\n        )\n        timings["memory_ms"] = (time.perf_counter() - started) * 1000\n\n        started = time.perf_counter()\n        chunks = self.documents.search(\n            principal,\n            question,\n            int(self.cfg.get("max_document_chunks", 8)),\n            float(self.cfg.get("document_min_score", 0.18)),\n        )\n        timings["rag_ms"] = (time.perf_counter() - started) * 1000\n'''
    if start in s:
        repl2='''        started = time.perf_counter()\n        retrieval_rules = []\n        retrieval_stats = {}\n        if self.advanced_retrieval is not None:\n            bundle = self.advanced_retrieval.retrieve(principal, question)\n            memories = bundle.memories\n            chunks = bundle.chunks\n            retrieval_rules = bundle.rules\n            retrieval_stats = bundle.stats\n        else:\n            memories = self.memory.search(\n                principal, question, int(self.cfg.get("max_memories", 6)), float(self.cfg.get("memory_min_score", 0.20))\n            )\n            chunks = self.documents.search(\n                principal, question, int(self.cfg.get("max_document_chunks", 8)), float(self.cfg.get("document_min_score", 0.18))\n            )\n        elapsed_retrieval = (time.perf_counter() - started) * 1000\n        timings["memory_ms"] = elapsed_retrieval\n        timings["rag_ms"] = elapsed_retrieval\n        timings["advanced_retrieval"] = retrieval_stats\n'''
        s=s.replace(start,repl2,1)
    elif 'retrieval_stats = {}' not in s:
        raise RuntimeError('context: bloque retrieval no reconocido')

    marker='''        if structured:\n'''
    if 'REGLAS EMPRESARIALES VALIDADAS RECUPERADAS' not in s:
        if marker not in s: raise RuntimeError('context: marker structured no encontrado')
        rules_block='''        if retrieval_rules:\n            lines = ["REGLAS EMPRESARIALES VALIDADAS RECUPERADAS (mayor prioridad que documentos/memoria):"]\n            for index, rule in enumerate(retrieval_rules, 1):\n                lines.append(f"[R{index}] {rule.get('name','Regla')} v{rule.get('version',1)} area={rule.get('area') or 'general'}: {rule.get('expression','')}")\n                sources.append({"type":"rule","rule_id":rule.get("id"),"name":rule.get("name"),"version":rule.get("version"),"area":rule.get("area"),"source_type":rule.get("source_type"),"source_ref":rule.get("source_ref"),"score":rule.get("retrieval_score")})\n            blocks.append("\\n".join(lines))\n\n'''
        s=s.replace(marker,rules_block+marker,1)

    # El limite final sigue existiendo como defensa dura; el engine ya comprimio por fuente.
    path.write_text(s,encoding='utf-8')

def main(root: Path):
    root=root.resolve(); scripts=root/'scripts'; ent=scripts/'enterprise_ai'
    if not ent.exists(): raise RuntimeError('No existe enterprise_ai')
    bdir=root/'updates'/('pre_r10_7_rag_'+datetime.now().strftime('%Y%m%d_%H%M%S')); bdir.mkdir(parents=True,exist_ok=True)
    for p in [ent/'factory.py',ent/'context_engine.py',root/'VERSION.txt']:
        backup(p,root,bdir)
    shutil.copy2(HERE/'advanced_retrieval.py',ent/'advanced_retrieval.py')
    patch_factory(ent/'factory.py'); patch_context(ent/'context_engine.py')
    (root/'VERSION.txt').write_text('8.5.5-r10.7-advanced-rag\n',encoding='utf-8')
    print(f'Backup: {bdir}')
    print('R10.7 patch OK')

if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('--root',required=True); args=ap.parse_args(); main(Path(args.root))
