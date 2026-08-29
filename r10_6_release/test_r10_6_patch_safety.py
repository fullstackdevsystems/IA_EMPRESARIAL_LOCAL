import tempfile
from pathlib import Path
import importlib.util
spec=importlib.util.spec_from_file_location('u',Path(__file__).parent/'apply_r10_6.py'); u=importlib.util.module_from_spec(spec); spec.loader.exec_module(u)

def run():
  with tempfile.TemporaryDirectory() as td:
    td=Path(td)
    f=td/'factory.py'; f.write_text('''from .semantic_registry import SemanticRegistry\nclass Components:\n    def __init__(self, cfg, db, llm, embeddings, vectors, memory, datasets, documents, governance, precedence, semantic, context, service, logger):\n        self.semantic = semantic\n    \n    \ndef x():\n    semantic = SemanticRegistry(precedence)\n    datasets = StructuredDataService(db, llm, governance=governance, precedence=precedence)\n    return Components(cfg, db, llm, embeddings, vectors, memory, datasets, documents, governance, precedence, semantic, context, service, logger)\n''')
    u.patch_factory(f); s=f.read_text(); assert 'AnalyticRuleEngine' in s and 'self.analytics = analytics' in s and 'analytics=analytics' in s
    print('PASS factory_wires_analytic_engine')

    b=td/'bi.py'; b.write_text('''from typing import Any, Dict, Optional, Tuple, List\nimport pandas as pd\ndef prepare_business(df: pd.DataFrame, roles: Dict[str, Optional[str]]) -> Tuple[pd.DataFrame, Dict[str, Any], List[str]]:\n    work = df.copy()\n    notes: List[str] = []\n    derived: Dict[str, Any] = {'roles_bi': roles.copy()}\n    if '_ventas' in work.columns and '_costo' in work.columns:\n        work['_utilidad'] = work['_ventas'] - work['_costo']\n        derived['utilidad'] = 'ventas - costo total'\n    if '_cantidad' in work.columns:\n        pass\n    return work, derived, notes\n''')
    u.patch_bi(b); s=b.read_text(); assert 'analytic_context' in s and "derived['reglas_metricas']" in s and 'reglas_filtro' in s
    print('PASS bi_has_filter_and_metric_hooks')

    uv=td/'universal.py'; uv.write_text('''from typing import Any, Dict, Optional\ndef analyze_file(path: Path, prompt: str, semantic_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:\n    work, derived_bi, bi_notes = bi.prepare_business(original, roles_bi)\n''')
    u.patch_universal(uv); s=uv.read_text(); assert 'analytic_context' in s and 'prepare_business(original, roles_bi, analytic_context)' in s
    print('PASS universal_passes_analytic_context')
  print('3/3 PASS R10.6 PATCH SAFETY')
if __name__=='__main__': run()
