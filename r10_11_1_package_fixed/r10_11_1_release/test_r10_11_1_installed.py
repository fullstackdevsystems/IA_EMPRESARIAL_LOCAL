from pathlib import Path
import py_compile, sys
root=Path(sys.argv[1]).resolve()
files=[
 root/"scripts"/"data_contract.py",
 root/"scripts"/"universal_prompt_engine.py",
 root/"scripts"/"analizador_universal.py",
 root/"scripts"/"bi_productivo.py",
 root/"scripts"/"analizador_app.py",
]
for f in files:
    py_compile.compile(str(f),doraise=True)
u=files[1].read_text(encoding="utf-8-sig")
a=files[2].read_text(encoding="utf-8-sig")
b=files[3].read_text(encoding="utf-8-sig")
app=files[4].read_text(encoding="utf-8-sig")
checks={
"installed_compile":all(f.exists() for f in files),
"installed_date_guard":"Parse only values that already look like calendar dates." in u,
"installed_contract":"validate_workbook_contract" in a,
"installed_real_profit":"utilidad_fuente" in b and "columna_real" in b,
"installed_real_freight":"freight_total" in b,
"installed_error_trace":"ANALYZER ERROR" in app and "analizador.err.log" in app,
"installed_version":(root/"VERSION.txt").read_text(encoding="utf-8").strip()=="8.5.5-r10.11.1-data-contract-hotfix",
}
for k,v in checks.items():
    assert v,k
    print("PASS",k)
print(f"{len(checks)}/{len(checks)} PASS R10.11.1 INSTALLED")
