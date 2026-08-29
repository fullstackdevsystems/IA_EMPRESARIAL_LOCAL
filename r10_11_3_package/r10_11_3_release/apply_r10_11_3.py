from __future__ import annotations
from pathlib import Path
import re
import sys

root = Path(sys.argv[1]).resolve()
scripts = root / "scripts"
pep = scripts / "prompt_execution_plan.py"
dash = scripts / "dashboard_dynamic.py"
version = root / "VERSION.txt"

def read(p: Path) -> str:
    return p.read_text(encoding="utf-8-sig")

def write(p: Path, text: str) -> None:
    p.write_text(text, encoding="utf-8")

# ------------------------------------------------------------------
# 1) Execution Plan must use the same governed semantic contract
# ------------------------------------------------------------------
t = read(pep)
import_line = "from semantic_contract_enforcer import enforce_semantic_contract\n"
if import_line not in t:
    anchor = "from universal_prompt_engine import compile_universal_plan\n"
    if anchor not in t:
        raise RuntimeError("No se encontro import de compile_universal_plan en prompt_execution_plan.py")
    t = t.replace(anchor, anchor + import_line, 1)

old = '    plan = compile_universal_plan(df, prompt, sheet=sheet)\n'
new = (
    '    plan = compile_universal_plan(df, prompt, sheet=sheet)\n'
    '    plan = enforce_semantic_contract(plan, df, prompt)\n'
)
if "plan = enforce_semantic_contract(plan, df, prompt)" not in t:
    if old not in t:
        raise RuntimeError("No se encontro la construccion del execution plan")
    t = t.replace(old, new, 1)

# Identify execution plan as governed without changing component semantics.
t = t.replace('"version": "r10.2",', '"version": "r10.11.3",', 1)
t = t.replace(
    '"mode": "universal-prompt-driven",',
    '"mode": "universal-prompt-driven+strict-semantic-contract",',
    1
)
write(pep, t)

# ------------------------------------------------------------------
# 2) Finish static mojibake cleanup in dashboard renderer.
# Only string literals/UI text are changed; formulas/column names untouched.
# ------------------------------------------------------------------
t = read(dash)
replacements = {
    "MÃ¡s": "Más",
    "cÃ¡lculo": "cálculo",
    "CÃ¡lculo": "Cálculo",
    "anÃ¡lisis": "análisis",
    "AnÃ¡lisis": "Análisis",
    "MatemÃ¡tica": "Matemática",
    "SemÃ¡ntico": "Semántico",
    "semÃ¡ntica": "semántica",
    "determinÃ­stica": "determinística",
    "SelecciÃ³n": "Selección",
    "selecciÃ³n": "selección",
    "PÃ¡gina": "Página",
    "PolÃ­tica": "Política",
    "AgrupaciÃ³n": "Agrupación",
    "MÃ©trica": "Métrica",
    "mÃ©trica": "métrica",
    "MÃ¡ximo": "Máximo",
    "MÃ­nimo": "Mínimo",
    "Ãšnicos": "Únicos",
    "Ãºnicos": "únicos",
    "AlmacÃ©n": "Almacén",
    "CategorÃ­as": "Categorías",
    "PÃ©rdida": "Pérdida",
    "pÃ©rdida": "pérdida",
    "invÃ¡lidas": "inválidas",
    "vÃ¡lidas": "válidas",
    "explÃ­citos": "explícitos",
    "mÃ¡s": "más",
    "GrÃ¡fica": "Gráfica",
    "âš": "⚠",
    "â–²": "▲",
    "â–¼": "▼",
}
for bad, good in replacements.items():
    t = t.replace(bad, good)

# Guard against the known recurring mojibake families in static UI.
known_bad = [
    "MÃ¡s", "cÃ¡lculo", "anÃ¡lisis", "MatemÃ¡tica", "SemÃ¡ntico",
    "determinÃ­stica", "PÃ¡gina", "PolÃ­tica", "MÃ©trica",
    "PÃ©rdida", "AlmacÃ©n", "CategorÃ­as"
]
remaining = [x for x in known_bad if x in t]
if remaining:
    raise RuntimeError("Mojibake conocido no corregido: " + ", ".join(remaining))
write(dash, t)

current = version.read_text(encoding="utf-8").strip() if version.exists() else ""
if "r10.12" in current.lower():
    final = "8.5.5-r10.12-controlled-finetune-dataset+hotfix-r10.11.3-plan-utf8"
else:
    final = "8.5.5-r10.11.3-plan-utf8"
version.write_text(final + "\n", encoding="utf-8")

print("R10.11.3 patch OK")
print("Version:", final)
