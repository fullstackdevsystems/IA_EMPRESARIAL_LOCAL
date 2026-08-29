from pathlib import Path
from datetime import datetime
import shutil

ROOT = Path(__file__).resolve().parent
REPO = Path.cwd()
DYN = REPO / "IA_Local" / "scripts" / "dashboard_dynamic.py"
ANALYZER = REPO / "IA_Local" / "scripts" / "analizador_universal.py"
LOGO_DST = REPO / "IA_Local" / "scripts" / "assets" / "primos_cousins_logo.png"
HTML_SRC = ROOT / "dashboard_template_r9_2.html.txt"
LOGO_SRC = ROOT / "primos_cousins_logo.png"

if not DYN.exists():
    raise SystemExit(f"ERROR: No se encontró {DYN}. Ejecuta desde C:\\IA_EMPRESARIAL_LOCAL")

stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
backup = REPO / "_backup_r9_2" / stamp
backup.mkdir(parents=True, exist_ok=True)
for p in (DYN, ANALYZER, LOGO_DST):
    if p.exists(): shutil.copy2(p, backup / p.name)

text = DYN.read_text(encoding="utf-8")
new_html = HTML_SRC.read_text(encoding="utf-8")
marker = "_HTML = r" + chr(39)*3
start = text.find(marker)
if start < 0:
    raise SystemExit("ERROR: No se encontró la plantilla _HTML en dashboard_dynamic.py")
text = text[:start] + marker + new_html + chr(39)*3 + '\n'
DYN.write_text(text, encoding="utf-8")
LOGO_DST.parent.mkdir(parents=True, exist_ok=True)
shutil.copy2(LOGO_SRC, LOGO_DST)

if ANALYZER.exists():
    a = ANALYZER.read_text(encoding="utf-8")
    a = a.replace("8.5.5-r9.1", "8.5.5-r9.2")
    a = a.replace("V8.5.5 R9.1", "V8.5.5 R9.2")
    ANALYZER.write_text(a, encoding="utf-8")

print("R9.2 DISEÑO aplicado correctamente.")
print("Backup:", backup)
print("Dashboard:", DYN)
print("Logo original:", LOGO_DST)
print("Version objetivo: 8.5.5-r9.2")
