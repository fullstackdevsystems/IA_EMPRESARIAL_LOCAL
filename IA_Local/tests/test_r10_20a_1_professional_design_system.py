from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]; S=ROOT/"scripts"; sys.path.insert(0,str(S))
from enterprise_design_system import *
def ck(n,x):
 if not x: raise AssertionError(n)
 print("PASS",n)
ck("version",DESIGN_SYSTEM_VERSION=="r10.20a")
for theme in ("professional-light","professional-dark"):
 t=get_design_tokens(theme); ck(theme,all(k in t["colors"] for k in ["primary","accent","success","warning","danger","background","surface","border","text_primary","text_secondary"]))
for status in ("SUPPORTED","DERIVABLE","BLOCKED","UNRESOLVED","CONFLICT"): ck(status,status_presentation(status)["symbol"])
css=build_dashboard_css(); ck("css", "--ds-primary" in css and "@media print" in css)
source=(S/"dashboard_dynamic.py").read_text(encoding="utf8"); ck("integration","enterprise_design_system" in source and "build_dashboard_css" in source); ck("offline","google fonts" not in css.lower() and "http" not in css.lower()); ck("neutral_brand","IA Empresarial Local" in source); ck("business_agnostic",all(x not in (S/"enterprise_design_system.py").read_text(encoding="utf8").lower() for x in ["ventas","clientes","flete","vendedores"]))
print("PASS R10.20A.1")
