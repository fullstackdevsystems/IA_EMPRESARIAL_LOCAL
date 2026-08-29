from __future__ import annotations
from pathlib import Path
import re
import sys

root = Path(sys.argv[1]).resolve()
scripts = root / 'scripts'
dash = scripts / 'dashboard_dynamic.py'
app = scripts / 'analizador_app.py'
version = root / 'VERSION.txt'

def read(p):
    return p.read_text(encoding='utf-8-sig')

def write(p, s):
    p.write_text(s, encoding='utf-8')

# JSON robusto
t = read(dash)
if 'def _json_default(v: Any)' not in t:
    start = t.find('def _safe_inline_json(')
    if start < 0:
        raise RuntimeError('No se encontro _safe_inline_json')
    next_def = t.find('\ndef ', start + 1)
    if next_def < 0:
        next_def = len(t)
    replacement = """def _json_default(v: Any) -> Any:
    if isinstance(v, pd.Timestamp):
        return None if pd.isna(v) else v.isoformat()
    if isinstance(v, Path):
        return str(v)
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
    except Exception:
        pass
    if hasattr(v, 'item'):
        try:
            native = v.item()
            if native is not v:
                return native
        except Exception:
            pass
    if hasattr(v, 'tolist'):
        try:
            return v.tolist()
        except Exception:
            pass
    return str(v)

def _safe_inline_json(obj: Any) -> str:
    s = json.dumps(obj, ensure_ascii=False, separators=(',', ':'), default=_json_default)
    return s.replace('</', '<\\/')
"""
    t = t[:start] + replacement + '\n' + t[next_def+1:]
elif 'default=_json_default' not in t:
    t = t.replace("json.dumps(obj, ensure_ascii=False, separators=(',', ':'))", "json.dumps(obj, ensure_ascii=False, separators=(',', ':'), default=_json_default)", 1)

if 'def _json_default(v: Any)' not in t or 'default=_json_default' not in t:
    raise RuntimeError('Serializacion JSON robusta no aplicada')
write(dash, t)

# ROOT flexible
t = read(app)
target = 'ROOT = Path(os.environ.get("IA_LOCAL_ROOT", str(Path(__file__).resolve().parent.parent))).resolve()'
if 'Path(__file__).resolve().parent.parent' not in t:
    lines = t.splitlines()
    hits = [i for i, line in enumerate(lines) if line.lstrip().startswith('ROOT') and 'IA_LOCAL_ROOT' in line]
    if len(hits) != 1:
        raise RuntimeError(f'No se pudo localizar ROOT de forma segura. Coincidencias={len(hits)}')
    lines[hits[0]] = target
    t = '\n'.join(lines) + ('\n' if t.endswith('\n') else '')
if target not in t:
    raise RuntimeError('ROOT no quedo relativo a la instalacion')
write(app, t)

current = version.read_text(encoding='utf-8').strip() if version.exists() else ''
if 'r10.12' in current.lower():
    final = '8.5.5-r10.12-controlled-finetune-dataset+hotfix-r10.11.1-data-contract-v6'
else:
    final = '8.5.5-r10.11.1-data-contract-hotfix-v6'
version.write_text(final + '\n', encoding='utf-8')
print('R10.11.1 V6 patch OK')
print('Version:', final)