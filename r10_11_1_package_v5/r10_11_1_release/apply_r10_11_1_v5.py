from __future__ import annotations
from pathlib import Path
import sys

root = Path(sys.argv[1]).resolve()
scripts = root / "scripts"
dash = scripts / "dashboard_dynamic.py"
app = scripts / "analizador_app.py"
version = root / "VERSION.txt"

def read(p):
    return p.read_text(encoding="utf-8-sig")

def write(p, s):
    p.write_text(s, encoding="utf-8")

t = read(dash)

old = '''def _safe_inline_json(obj: Any) -> str:
    s = json.dumps(obj, ensure_ascii=False, separators=(',', ':'))
    return s.replace('</', '<\\\\/')
'''

new = '''def _json_default(v: Any) -> Any:
    # Convierte escalares Pandas/NumPy a tipos nativos serializables por JSON.
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
    return s.replace('</', '<\\\\/')
'''

if old in t:
    t = t.replace(old, new, 1)
elif "def _json_default(v: Any)" not in t:
    raise RuntimeError("No se pudo localizar _safe_inline_json en dashboard_dynamic.py")

write(dash, t)

t = read(app)
old_root = 'ROOT = Path(os.environ.get("IA_LOCAL_ROOT", r"C:\\\\IA_Local"))'
new_root = 'ROOT = Path(os.environ.get("IA_LOCAL_ROOT", str(Path(__file__).resolve().parent.parent))).resolve()'

if old_root in t:
    t = t.replace(old_root, new_root, 1)
elif "Path(__file__).resolve().parent.parent" not in t:
    raise RuntimeError("No se pudo localizar ROOT en analizador_app.py")

write(app, t)

current = version.read_text(encoding="utf-8").strip() if version.exists() else ""
if "r10.12" in current.lower():
    final = "8.5.5-r10.12-controlled-finetune-dataset+hotfix-r10.11.1-data-contract-v5"
else:
    final = "8.5.5-r10.11.1-data-contract-hotfix-v5"

version.write_text(final + "\\n", encoding="utf-8")
print("R10.11.1 V5 patch OK")
print("Version:", final)
