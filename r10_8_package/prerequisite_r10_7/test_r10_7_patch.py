from pathlib import Path
import tempfile, sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import apply_r10_7 as p

def test_factory_patch():
    s='from .context_engine import ContextEngine\n\ndef f():\n    context = ContextEngine(memory, documents, datasets, cfg.section("retrieval"))\n'
    with tempfile.TemporaryDirectory() as td:
        f=Path(td)/'factory.py'; f.write_text(s); p.patch_factory(f); x=f.read_text(); assert 'AdvancedRetrievalEngine' in x and 'advanced_retrieval=advanced_retrieval' in x

def test_context_patch():
    s='''from typing import Any, Dict\nclass ContextEngine:\n    def __init__(self, memory: MemoryManager, documents: DocumentService, structured: StructuredDataService, retrieval_cfg: Dict[str, Any]):\n        self.memory = memory\n        self.documents = documents\n        self.structured = structured\n        self.cfg = retrieval_cfg\n    def build(self, principal, question):\n        timings={}\n        started = time.perf_counter()\n        memories = self.memory.search(\n            principal,\n            question,\n            int(self.cfg.get("max_memories", 6)),\n            float(self.cfg.get("memory_min_score", 0.20)),\n        )\n        timings["memory_ms"] = (time.perf_counter() - started) * 1000\n\n        started = time.perf_counter()\n        chunks = self.documents.search(\n            principal,\n            question,\n            int(self.cfg.get("max_document_chunks", 8)),\n            float(self.cfg.get("document_min_score", 0.18)),\n        )\n        timings["rag_ms"] = (time.perf_counter() - started) * 1000\n        sources=[]; blocks=[]\n        structured=None\n        if structured:\n            pass\n'''
    with tempfile.TemporaryDirectory() as td:
        f=Path(td)/'context_engine.py'; f.write_text(s); p.patch_context(f); x=f.read_text(); assert 'advanced_retrieval' in x and 'REGLAS EMPRESARIALES VALIDADAS RECUPERADAS' in x

if __name__=='__main__':
    tests=[v for k,v in globals().items() if k.startswith('test_') and callable(v)]
    for t in tests:t();print('PASS',t.__name__)
    print(f'{len(tests)}/{len(tests)} PASS R10.7 PATCH')
