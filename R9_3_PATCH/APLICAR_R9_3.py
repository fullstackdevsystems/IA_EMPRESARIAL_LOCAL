from pathlib import Path
from datetime import datetime
import shutil

ROOT = Path(__file__).resolve().parent
REPO = Path.cwd()

GUARD_DST = REPO / "IA_Local" / "scripts" / "dashboard_prompt_guard.py"
TESTS = REPO / "IA_Local" / "tests" / "test_bi_productivo.py"
ANALYZER = REPO / "IA_Local" / "scripts" / "analizador_universal.py"

if not GUARD_DST.exists():
    raise SystemExit("ERROR: No se encontró dashboard_prompt_guard.py. Debe estar aplicada R9.1/R9.2.")

stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
backup = REPO / "_backup_r9_3" / stamp
backup.mkdir(parents=True, exist_ok=True)

for p in (GUARD_DST, TESTS, ANALYZER):
    if p.exists():
        shutil.copy2(p, backup / p.name)

shutil.copy2(ROOT / "dashboard_prompt_guard.py", GUARD_DST)

tests = TESTS.read_text(encoding="utf-8")
marker = "def test_r9_3_names_previous_does_not_trigger_previous_comparison():"
if marker not in tests:
    addition = (ROOT / "tests_r9_3_append.txt").read_text(encoding="utf-8").rstrip() + "\n\n"
    needle = "\nif __name__=='__main__':"
    if needle not in tests:
        raise SystemExit("ERROR: no se encontró __main__ en test_bi_productivo.py")
    tests = tests.replace(needle, "\n" + addition + "if __name__=='__main__':", 1)
    TESTS.write_text(tests, encoding="utf-8")

if ANALYZER.exists():
    a = ANALYZER.read_text(encoding="utf-8")
    a = a.replace("8.5.5-r9.2", "8.5.5-r9.3")
    a = a.replace("V8.5.5 R9.2", "V8.5.5 R9.3")
    ANALYZER.write_text(a, encoding="utf-8")

print("R9.3 aplicado correctamente.")
print("Backup:", backup)
print("Guard actualizado:", GUARD_DST)
print("Version objetivo: 8.5.5-r9.3")
print("Nuevas pruebas agregadas: 3")
