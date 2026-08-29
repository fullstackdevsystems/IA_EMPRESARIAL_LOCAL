from pathlib import Path
import tempfile, sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import apply_r10_8 as a

def run():
  with tempfile.TemporaryDirectory() as td:
    root=Path(td); ent=root/'scripts'/'enterprise_ai'; ent.mkdir(parents=True)
    # Forma representativa después de R10.6/R10.7.
    factory='''from .context_engine import ContextEngine\nfrom .knowledge_governance import KnowledgeGovernance\nclass Components:\n    def __init__(self, cfg, db, llm, embeddings, vectors, memory, datasets, documents, governance, precedence, semantic, analytics, context, service, logger):\n        self.memory = memory\n        self.datasets = datasets\ndef build_components():\n    memory = MemoryManager(db, embeddings, vectors)\n    governance = KnowledgeGovernance(db)\n    precedence = PrecedenceEngine(governance)\n    semantic = SemanticRegistry(precedence)\n    analytics = AnalyticRuleEngine(db, governance, precedence)\n    datasets = StructuredDataService(db, llm, governance=governance, precedence=precedence, analytics=analytics)\n    documents = DocumentService(cfg, db, embeddings, vectors, datasets)\n    advanced_retrieval = AdvancedRetrievalEngine(memory, documents, governance, cfg.section("retrieval"))\n    context = ContextEngine(memory, documents, datasets, cfg.section("retrieval"), advanced_retrieval=advanced_retrieval)\n    service = EnterpriseAIService(cfg, db, llm, memory, context)\n    return Components(cfg, db, llm, embeddings, vectors, memory, datasets, documents, governance, precedence, semantic, analytics, context, service, logger)\n'''
    (ent/'factory.py').write_text(factory,encoding='utf-8')
    api='''from typing import Any, Dict, List, Optional\nclass BaseModel: pass\nclass Field:\n  def __init__(self,*a,**k):pass\nclass SettingsRequest(BaseModel):\n    pass\nASSISTANT_HTML = r\"\"\"<script>function sourceHtml(d){return ''} function x(){src.innerHTML=sourceHtml(ev);bubble.appendChild(src);hist.push({role:'user',content:m},{role:'assistant',content:answer});}</script>\"\"\"\ndef f():\n    @router.get(\"/api/enterprise/settings\")\n    def settings(principal=None): pass\n'''
    (ent/'api.py').write_text(api,encoding='utf-8')
    a.patch_factory(ent/'factory.py');a.patch_api(ent/'api.py')
    fs=(ent/'factory.py').read_text(); ap=(ent/'api.py').read_text()
    assert 'memory, feedback, datasets' in fs and 'self.feedback = feedback' in fs
    assert 'governance = KnowledgeGovernance(db)\n    feedback = FeedbackManager(db, memory, governance)' in fs
    assert 'memory, feedback, datasets, documents, governance' in fs
    print('PASS factory_feedback_wiring_r10_7_shape')
    assert '/api/enterprise/feedback/{feedback_id}/validate' in ap
    print('PASS feedback_endpoints')
    assert 'feedbackButtons' in ap and 'Guardar / Validar' in ap
    print('PASS assistant_feedback_controls')
    print('3/3 PASS R10.8 PATCH')
if __name__=='__main__':run()
