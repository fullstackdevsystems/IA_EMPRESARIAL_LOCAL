from pathlib import Path
import sys
root=Path(sys.argv[1]).resolve(); scripts=root/'scripts'; sys.path.insert(0,str(scripts))
checks=[]
checks.append(('advanced_retrieval_exists',(scripts/'enterprise_ai'/'advanced_retrieval.py').exists()))
factory=(scripts/'enterprise_ai'/'factory.py').read_text(encoding='utf-8')
context=(scripts/'enterprise_ai'/'context_engine.py').read_text(encoding='utf-8')
checks.append(('factory_wired','AdvancedRetrievalEngine' in factory and 'advanced_retrieval=advanced_retrieval' in factory))
checks.append(('context_wired','self.advanced_retrieval' in context and 'retrieval_stats' in context))
checks.append(('rule_sources','"type":"rule"' in context or '"type": "rule"' in context))
checks.append(('version',(root/'VERSION.txt').read_text().strip()=='8.5.5-r10.7-advanced-rag'))
failed=[]
for n,ok in checks:
    print(('PASS ' if ok else 'FAIL ')+n)
    if not ok: failed.append(n)
if failed: raise SystemExit(1)
print(f'{len(checks)}/{len(checks)} PASS R10.7 INSTALLED')
