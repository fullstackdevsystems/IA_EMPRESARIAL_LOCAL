from pathlib import Path
import shutil
from datetime import datetime

ROOT = Path(__file__).resolve().parent
REPO = Path.cwd()
TARGET = REPO / "IA_Local" / "scripts" / "dashboard_dynamic.py"
TESTS = REPO / "IA_Local" / "tests" / "test_bi_productivo.py"
ANALYZER = REPO / "IA_Local" / "scripts" / "analizador_universal.py"
GUARD_SRC = ROOT / "dashboard_prompt_guard.py"
GUARD_DST = REPO / "IA_Local" / "scripts" / "dashboard_prompt_guard.py"
TEST_APPEND = ROOT / "tests_append_r9_1.txt"

if not TARGET.exists():
    raise SystemExit(f"ERROR: no se encontró {TARGET}. Ejecuta este parche desde C:\\IA_EMPRESARIAL_LOCAL")

stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
backup_dir = REPO / "_backup_r9_1" / stamp
backup_dir.mkdir(parents=True, exist_ok=True)
for p in (TARGET, TESTS, ANALYZER):
    if p.exists():
        shutil.copy2(p, backup_dir / p.name)

shutil.copy2(GUARD_SRC, GUARD_DST)
text = TARGET.read_text(encoding="utf-8")
text = text.replace("if t and (t in nc or nc in t):", "if t and t in nc:")
text = text.replace("}, timeout=12)", "}, timeout=float(os.getenv('IA_DYNAMIC_DASHBOARD_TIMEOUT','90')))")

old_build = """def build_dashboard_plan(df: pd.DataFrame, prompt: str, filename: str = '', sheet: str = '') -> Dict[str, Any]:
    fallback = _fallback_plan(df, prompt, filename, sheet)
    ai_plan = _ollama_plan(df, prompt, filename, sheet)
    return _validate_plan(ai_plan, df, fallback)
"""
new_build = """def build_dashboard_plan(df: pd.DataFrame, prompt: str, filename: str = '', sheet: str = '') -> Dict[str, Any]:
    fallback = _fallback_plan(df, prompt, filename, sheet)
    ai_plan = _ollama_plan(df, prompt, filename, sheet)
    validated = _validate_plan(ai_plan, df, fallback)
    from dashboard_prompt_guard import enforce_prompt_contract
    return enforce_prompt_contract(validated, df, prompt, filename, sheet)
"""

if old_build in text:
    text = text.replace(old_build, new_build)
elif "from dashboard_prompt_guard import enforce_prompt_contract" not in text:
    raise SystemExit("ERROR: no se encontró build_dashboard_plan esperado; no se aplicó el parche.")

TARGET.write_text(text, encoding="utf-8")

tests = TESTS.read_text(encoding="utf-8")
marker = "def test_r9_1_prompt_contract_blocks_fake_budget_and_previous():"
if marker not in tests:
    insertion = TEST_APPEND.read_text(encoding="utf-8").rstrip() + "\n\n"
    needle = "\nif __name__=='__main__':"
    if needle not in tests:
        raise SystemExit("ERROR: no se encontró el bloque __main__ de pruebas.")
    tests = tests.replace(needle, "\n" + insertion + "if __name__=='__main__':", 1)
    TESTS.write_text(tests, encoding="utf-8")

if ANALYZER.exists():
    a = ANALYZER.read_text(encoding="utf-8")
    a = a.replace("8.5.5-r9", "8.5.5-r9.1")
    a = a.replace("V8.5.5 R9 · Dashboard Dinámico IA", "V8.5.5 R9.1 · Dashboard Dinámico IA")
    a = a.replace("V8.5.5 R9</span>", "V8.5.5 R9.1</span>")
    a = a.replace("prompt driven + calculo deterministico + semantic mapper + aislamiento empresa/usuario",
                  "prompt authority + data contract + calculo deterministico + semantic mapper + aislamiento empresa/usuario")
    ANALYZER.write_text(a, encoding="utf-8")

print("R9.1 aplicado correctamente.")
print("Backup:", backup_dir)
print("Nuevo módulo:", GUARD_DST)
print("Ejecuta ahora las suites de pruebas.")
