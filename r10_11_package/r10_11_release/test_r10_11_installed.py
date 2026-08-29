from pathlib import Path
import py_compile, sys
root=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else Path.cwd()
files=[root/'scripts/enterprise_ai/performance.py',root/'scripts/enterprise_ai/structured_data.py',root/'scripts/enterprise_ai/api.py']
for p in files: py_compile.compile(str(p),doraise=True)
print('PASS installed_compile')
text=(root/'scripts/enterprise_ai/structured_data.py').read_text(encoding='utf-8')
assert 'try_execute_large_query' in text; print('PASS installed_streaming_path')
api=(root/'scripts/enterprise_ai/api.py').read_text(encoding='utf-8')
assert '/api/enterprise/performance' in api; print('PASS installed_performance_api')
ver=(root/'VERSION.txt').read_text(encoding='utf-8').strip()
assert ver=='8.5.5-r10.11-large-data'; print('PASS installed_version')
print('4/4 PASS R10.11 INSTALLED')
