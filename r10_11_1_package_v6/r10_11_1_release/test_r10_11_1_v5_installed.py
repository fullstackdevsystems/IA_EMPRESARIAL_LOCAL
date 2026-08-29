from pathlib import Path
import py_compile, sys

root=Path(sys.argv[1]).resolve()
dash=root/"scripts"/"dashboard_dynamic.py"
app=root/"scripts"/"analizador_app.py"

for f in (dash,app):
    py_compile.compile(str(f), doraise=True)

dt=dash.read_text(encoding="utf-8-sig")
at=app.read_text(encoding="utf-8-sig")

checks={
    "dashboard_compile": True,
    "json_default": "def _json_default(v: Any)" in dt,
    "json_default_hook": "default=_json_default" in dt,
    "numpy_scalar_support": "hasattr(v, 'item')" in dt,
    "root_relative": "Path(__file__).resolve().parent.parent" in at,
    "root_env_override": 'os.environ.get("IA_LOCAL_ROOT"' in at,
}

for k,v in checks.items():
    assert v,k
    print("PASS",k)

print(f"{len(checks)}/{len(checks)} PASS R10.11.1 V5 INSTALLED")
