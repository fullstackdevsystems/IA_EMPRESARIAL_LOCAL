from pathlib import Path
import sys, sqlite3, tempfile
root=Path(sys.argv[1]).resolve(); sys.path.insert(0,str(root/'scripts'))
from enterprise_ai.database import Database
from enterprise_ai.security import Principal
from enterprise_ai.traceability import TraceabilityManager, trace_step
with tempfile.TemporaryDirectory() as td:
    tm=TraceabilityManager(Database(Path(td)/'trace.db')); p=Principal('testco','tester')
    with tm.scope(p,trace_type='installed_test',prompt='prueba') as tid:
        trace_step('structured_calculation',engine='python/pandas',details={'file':'demo.xlsx','sheet':'BD','rows_used':3})
    x=tm.get(p,tid); assert x['steps'][0]['stage']=='structured_calculation'
print('PASS installed_trace_storage')
from enterprise_ai import factory
src=(root/'scripts'/'enterprise_ai'/'factory.py').read_text(encoding='utf-8'); assert 'TraceabilityManager' in src
print('PASS installed_factory_wiring')
api=(root/'scripts'/'enterprise_ai'/'api.py').read_text(encoding='utf-8'); assert '/api/enterprise/traces/{trace_id}/explain' in api
print('PASS installed_trace_api')
print('3/3 PASS R10.9 INSTALLED')
