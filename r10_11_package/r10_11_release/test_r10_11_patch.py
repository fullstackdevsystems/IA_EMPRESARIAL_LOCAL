from pathlib import Path
import tempfile, shutil, sys
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from apply_r10_11 import patch_structured, patch_api

def check(n,c):
    if not c: raise AssertionError(n)
    print('PASS',n)
with tempfile.TemporaryDirectory() as td:
    td=Path(td)
    s=td/'structured_data.py'; s.write_text('class X:\n    def q(self):\n        df, sheet = self._load(dataset)\n',encoding='utf-8')
    patch_structured(s); t=s.read_text(encoding='utf-8')
    check('structured_fast_path','try_execute_large_query' in t and 'pandas-chunked' in t)
    a=td/'api.py'; a.write_text('    @router.get("/api/enterprise/audit")\n    def audit(): pass\n',encoding='utf-8')
    patch_api(a); x=a.read_text(encoding='utf-8')
    check('performance_endpoint','/api/enterprise/performance' in x)
    check('admin_dependency','Depends(admin_dependency)' in x)
print('3/3 PASS R10.11 PATCH')
