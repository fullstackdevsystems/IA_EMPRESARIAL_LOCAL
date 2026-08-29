from __future__ import annotations
from pathlib import Path
import sys

root=Path(sys.argv[1]).resolve()
scripts=root/"scripts"
compiler=scripts/"enterprise_prompt_compiler.py"
dash=scripts/"dashboard_dynamic.py"
version=root/"VERSION.txt"

def read(p): return p.read_text(encoding="utf-8-sig")
def write(p,s): p.write_text(s,encoding="utf-8")

t=read(compiler)
if "from semantic_contract_enforcer import enforce_semantic_contract" not in t:
    t=t.replace(
        "from universal_prompt_engine import compile_universal_plan, norm\n",
        "from universal_prompt_engine import compile_universal_plan, norm\nfrom semantic_contract_enforcer import enforce_semantic_contract\n",
        1
    )
needle="    universal = compile_universal_plan(df, prompt, filename, sheet)\n"
if "universal = enforce_semantic_contract(universal, df, prompt)" not in t:
    if needle not in t:
        raise RuntimeError("No se localizo compile_universal_plan en enterprise_prompt_compiler.py")
    t=t.replace(needle, needle+"    universal = enforce_semantic_contract(universal, df, prompt)\n",1)
write(compiler,t)

t=read(dash)
replacements={
    "LogÃ­stica":"Logística","AnÃ¡lisis":"Análisis","validaciÃ³n":"validación","ValidaciÃ³n":"Validación",
    "automÃ¡ticamente":"automáticamente","automÃ¡tico":"automático","PregÃºntale":"Pregúntale",
    "cÃ¡lculos":"cálculos","selecciÃ³n":"selección","categorÃ­as":"categorías","cÃ³digo":"código",
    "grÃ¡ficas":"gráficas","GrÃ¡ficas":"Gráficas","Â·":"·","Â¿":"¿","QuÃ©":"Qué","CuÃ¡l":"Cuál",
    "â†’":"→","â€”":"—","âœ“":"✓","â‰¡":"≡","â‡„":"⇄","â–£":"▣","âŒ":"⌁",
    "â—«":"◫","â–¦":"▪","â—Ž":"◎","â—†":"◆","â†»":"↻","â—‰":"◉","â—":"●",
}
for bad,good in replacements.items():
    t=t.replace(bad,good)
write(dash,t)

cur=version.read_text(encoding="utf-8").strip() if version.exists() else ""
if "r10.12" in cur.lower():
    final="8.5.5-r10.12-controlled-finetune-dataset+hotfix-r10.11.2-semantic-contract"
else:
    final="8.5.5-r10.11.2-semantic-contract"
version.write_text(final+"\n",encoding="utf-8")
print("R10.11.2 patch OK")
print("Version:",final)
