from pathlib import Path
import sys,py_compile
root=Path(sys.argv[1]); ent=root/'scripts'/'enterprise_ai'
for name in ['admin_console.py','api.py']:
 p=ent/name; assert p.exists(),p; py_compile.compile(str(p),doraise=True)
s=(ent/'api.py').read_text(encoding='utf-8')
checks=['UNIFIED_ADMIN_HTML','/api/enterprise/admin/overview','/api/enterprise/business-rules','/api/enterprise/semantic-definitions','/api/enterprise/analytic-rules','/history']
for x in checks: assert x in s,x
assert (root/'VERSION.txt').read_text().strip()=='8.5.5-r10.10-unified-admin'
print('PASS installed_compile');print('PASS installed_admin_route');print('PASS installed_governance_api');print('PASS installed_version');print('4/4 PASS R10.10 INSTALLED')
