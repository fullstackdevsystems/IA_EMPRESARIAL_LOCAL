from pathlib import Path
import py_compile,sys
root=Path(sys.argv[1]).resolve()
files=[
 root/"scripts"/"semantic_contract_enforcer.py",
 root/"scripts"/"enterprise_prompt_compiler.py",
 root/"scripts"/"dashboard_dynamic.py",
]
for f in files: py_compile.compile(str(f),doraise=True)
enf=files[0].read_text(encoding="utf-8-sig")
comp=files[1].read_text(encoding="utf-8-sig")
dash=files[2].read_text(encoding="utf-8-sig")
checks={
 "installed_compile":True,
 "enforcer_hook":"enforce_semantic_contract(universal, df, prompt)" in comp,
 "strict_policy":"strict_semantic_map_precedence" in enf,
 "filter_contract":"product_group" in enf and "origin_city" in enf and "customer_pickup" in enf,
 "utf8_repaired":"LogÃ" not in dash and "ValidaciÃ" not in dash and "PregÃ" not in dash,
 "version":"r10.11.2-semantic-contract" in (root/"VERSION.txt").read_text(encoding="utf-8"),
}
for k,v in checks.items():
 assert v,k
 print("PASS",k)
print(f"{len(checks)}/{len(checks)} PASS R10.11.2 INSTALLED")
