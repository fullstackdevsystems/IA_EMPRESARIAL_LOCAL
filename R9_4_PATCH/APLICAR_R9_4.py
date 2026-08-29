from pathlib import Path
from datetime import datetime
import shutil

ROOT = Path(__file__).resolve().parent
REPO = Path.cwd()

DYN = REPO / "IA_Local" / "scripts" / "dashboard_dynamic.py"
COMP_DST = REPO / "IA_Local" / "scripts" / "enterprise_prompt_compiler.py"
TESTS = REPO / "IA_Local" / "tests" / "test_bi_productivo.py"
ANALYZER = REPO / "IA_Local" / "scripts" / "analizador_universal.py"

for p in (DYN, TESTS, ANALYZER):
    if not p.exists():
        raise SystemExit(f"ERROR: no se encontró {p}")

stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
backup = REPO / "_backup_r9_4" / stamp
backup.mkdir(parents=True, exist_ok=True)
for p in (DYN, TESTS, ANALYZER):
    shutil.copy2(p, backup / p.name)
if COMP_DST.exists():
    shutil.copy2(COMP_DST, backup / COMP_DST.name)

shutil.copy2(ROOT / "enterprise_prompt_compiler.py", COMP_DST)

text = DYN.read_text(encoding="utf-8")

old_return = "return enforce_prompt_contract(validated, df, prompt, filename, sheet)"
new_return = """guarded = enforce_prompt_contract(validated, df, prompt, filename, sheet)
    from enterprise_prompt_compiler import compile_enterprise_prompt
    return compile_enterprise_prompt(guarded, df, prompt, filename, sheet)"""
if new_return not in text:
    if old_return not in text:
        raise SystemExit("ERROR: no se encontró el punto de integración R9.3 en dashboard_dynamic.py")
    text = text.replace(old_return, new_return, 1)

old_js = "if(op==='ratio_pct'){const a=vals(k.numerator).reduce((x,y)=>x+y,0),b=vals(k.denominator).reduce((x,y)=>x+y,0);return b?100*a/b:0}"
new_js = "if(op==='ratio'){const a=vals(k.numerator).reduce((x,y)=>x+y,0),b=vals(k.denominator).reduce((x,y)=>x+y,0);return b?a/b:0}if(op==='ratio_pct'){const a=vals(k.numerator).reduce((x,y)=>x+y,0),b=vals(k.denominator).reduce((x,y)=>x+y,0);return b?100*a/b:0}"
if new_js not in text:
    if old_js not in text:
        raise SystemExit("ERROR: no se encontró el renderer KPI ratio_pct esperado en dashboard_dynamic.py")
    text = text.replace(old_js, new_js, 1)

DYN.write_text(text, encoding="utf-8")

tests = TESTS.read_text(encoding="utf-8")
marker = "def test_r9_4_enterprise_prompt_compiler_builds_full_plan():"
if marker not in tests:
    addition = (ROOT / "tests_r9_4_append.txt").read_text(encoding="utf-8").rstrip() + "\n\n"
    needle = "\nif __name__=='__main__':"
    if needle not in tests:
        raise SystemExit("ERROR: no se encontró __main__ en test_bi_productivo.py")
    tests = tests.replace(needle, "\n" + addition + "if __name__=='__main__':", 1)
    TESTS.write_text(tests, encoding="utf-8")

a = ANALYZER.read_text(encoding="utf-8")
a = a.replace("8.5.5-r9.3", "8.5.5-r9.4")
a = a.replace("V8.5.5 R9.3", "V8.5.5 R9.4")
ANALYZER.write_text(a, encoding="utf-8")

print("R9.4 aplicado correctamente.")
print("Backup:", backup)
print("Compilador:", COMP_DST)
print("Dashboard actualizado:", DYN)
print("Version objetivo: 8.5.5-r9.4")
