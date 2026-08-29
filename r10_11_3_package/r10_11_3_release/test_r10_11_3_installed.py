from pathlib import Path
import py_compile, sys

root=Path(sys.argv[1]).resolve()
pep=root/"scripts"/"prompt_execution_plan.py"
dash=root/"scripts"/"dashboard_dynamic.py"
version=root/"VERSION.txt"

for f in (pep,dash):
    py_compile.compile(str(f),doraise=True)

pt=pep.read_text(encoding="utf-8-sig")
dt=dash.read_text(encoding="utf-8-sig")
vt=version.read_text(encoding="utf-8").strip()

bad=[
 "MÃ¡s","cÃ¡lculo","anÃ¡lisis","MatemÃ¡tica","SemÃ¡ntico",
 "determinÃ­stica","PÃ¡gina","PolÃ­tica","MÃ©trica",
 "PÃ©rdida","AlmacÃ©n","CategorÃ­as"
]

checks={
 "installed_compile":True,
 "execution_enforcer_import":"from semantic_contract_enforcer import enforce_semantic_contract" in pt,
 "execution_enforcer_call":"plan = enforce_semantic_contract(plan, df, prompt)" in pt,
 "execution_version":'"version": "r10.11.3"' in pt,
 "execution_mode":"strict-semantic-contract" in pt,
 "utf8_cleanup":not any(x in dt for x in bad),
 "version":"r10.11.3-plan-utf8" in vt,
}
for k,v in checks.items():
    assert v,k
    print("PASS",k)
print(f"{len(checks)}/{len(checks)} PASS R10.11.3 INSTALLED")
