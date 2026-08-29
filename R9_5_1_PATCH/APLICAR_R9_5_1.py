from pathlib import Path
from datetime import datetime
import shutil, re

ROOT=Path(__file__).resolve().parent
REPO=Path.cwd()
DYN=REPO/"IA_Local"/"scripts"/"dashboard_dynamic.py"
ANA=REPO/"IA_Local"/"scripts"/"enterprise_analytics.py"
COMP=REPO/"IA_Local"/"scripts"/"enterprise_prompt_compiler.py"
TESTS=REPO/"IA_Local"/"tests"/"test_bi_productivo.py"
ANALYZER=REPO/"IA_Local"/"scripts"/"analizador_universal.py"

for p in (DYN,ANA,COMP,TESTS,ANALYZER):
    if not p.exists(): raise SystemExit(f"ERROR: falta {p}. Debe estar aplicada R9.5.")

stamp=datetime.now().strftime("%Y%m%d_%H%M%S")
backup=REPO/"_backup_r9_5_1"/stamp
backup.mkdir(parents=True,exist_ok=True)
for p in (DYN,ANA,COMP,TESTS,ANALYZER): shutil.copy2(p,backup/p.name)

a=ANA.read_text(encoding="utf-8")
old='"operaciones_negativas":len(neg),"impacto_negativo_visible":sum(_num(x.get("Utilidad")) for x in neg)'
new='"operaciones_negativas":int((pd.to_numeric(df["Utilidad"],errors="coerce").fillna(0.0)<0).sum()) if "Utilidad" in df.columns else 0,"impacto_negativo":float(pd.to_numeric(df.loc[pd.to_numeric(df["Utilidad"],errors="coerce").fillna(0.0)<0,"Utilidad"],errors="coerce").fillna(0.0).sum()) if "Utilidad" in df.columns else 0.0'
if old not in a and new not in a: raise SystemExit("ERROR: patrón de negativos no encontrado")
a=a.replace(old,new,1)
a=a.replace("Se detectaron {f.get('operaciones_negativas',0)} operaciones con utilidad negativa.","Se detectaron {f.get('operaciones_negativas',0)} operaciones con utilidad negativa, con impacto acumulado de {cur(f.get('impacto_negativo',0.0))}.")
ANA.write_text(a,encoding="utf-8")

d=DYN.read_text(encoding="utf-8")
d=d.replace("function render(){const r=filtered();renderKpis(r);renderCharts(r);renderTable(r);renderAdvanced()}","function render(){const r=filtered();renderKpis(r);renderCharts(r);renderTable(r);renderAdvanced(r)}",1)
reactive=(ROOT/"advanced_reactive_js.txt").read_text(encoding="utf-8").rstrip()
pattern=r"function metricTable\(rows,cols,limit=20\)\{.*?\}function openDrill"
m=re.search(pattern,d,flags=re.S)
if not m:
    if "function advGroup(rows,dims)" not in d: raise SystemExit("ERROR: bloque renderAdvanced R9.5 no encontrado")
else:
    d=d[:m.start()]+reactive+"\nfunction openDrill"+d[m.end():]
DYN.write_text(d,encoding="utf-8")

c=COMP.read_text(encoding="utf-8")
c=c.replace('"version":"r9.5"','"version":"r9.5.1"')
c=c.replace("enterprise-prompt-compiler-r9.5","enterprise-prompt-compiler-r9.5.1")
c=c.replace("R9.5 compiló métricas, filtros, visualizaciones y analítica avanzada desde el prompt.","R9.5.1 compiló métricas, filtros, visualizaciones y analítica avanzada reactiva desde el prompt.")
COMP.write_text(c,encoding="utf-8")

tests=TESTS.read_text(encoding="utf-8")
# Make cumulative version assertions forward-compatible with R9.5.1.
tests=tests.replace('assert plan["prompt_compiler"]["version"] in {"r9.4","r9.5"}', 'assert plan["prompt_compiler"]["version"] in {"r9.4","r9.5","r9.5.1"}')
tests=tests.replace('assert p["prompt_compiler"]["version"]=="r9.5"', 'assert p["prompt_compiler"]["version"] in {"r9.5","r9.5.1"}')
marker="def test_r9_5_1_renderer_recomputes_advanced_from_filtered_rows():"
if marker not in tests:
    add=(ROOT/"tests_r9_5_1_append.txt").read_text(encoding="utf-8").rstrip()+"\n\n"
    needle="\nif __name__=='__main__':"
    if needle not in tests: raise SystemExit("ERROR: no se encontró __main__")
    tests=tests.replace(needle,"\n"+add+"if __name__=='__main__':",1)
    TESTS.write_text(tests,encoding="utf-8")

an=ANALYZER.read_text(encoding="utf-8")
an=an.replace("8.5.5-r9.5","8.5.5-r9.5.1").replace("V8.5.5 R9.5","V8.5.5 R9.5.1")
ANALYZER.write_text(an,encoding="utf-8")

print("R9.5.1 aplicado correctamente.")
print("Backup:",backup)
print("Version objetivo: 8.5.5-r9.5.1")
