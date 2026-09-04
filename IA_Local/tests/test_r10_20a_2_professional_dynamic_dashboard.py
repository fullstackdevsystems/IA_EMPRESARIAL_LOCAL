from pathlib import Path
import sys,tempfile
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]; S=ROOT/"scripts"; sys.path.insert(0,str(S))
from dashboard_dynamic import generate_dynamic_dashboard
def ck(n,x):
 if not x: raise AssertionError(n)
 print("PASS",n)
with tempfile.TemporaryDirectory() as td:
 for name,rows in [("construction",[{"Proyecto":"A","Avance físico":50,"Presupuesto":100,"Estatus":"Activo"}]),("services",[{"Contrato":"S","SLA":99,"Incidencias":2,"Tiempo atención":4}]),("sales",[{"Cliente":"A","Ventas":100,"Producto":"P"}]),("logistics",[{"Ruta":"Norte","Unidad operativa":"U1","Carga":8}]),("operations",[{"Almacén":"Central","Existencia":20,"Movimiento":"Entrada"}]),("neutral",[{"Entidad":"X","Indicador":3,"Estado":"Activo"}])]:
  p=Path(td)/(name+".html"); generate_dynamic_dashboard(p,pd.DataFrame(rows),"resumen",name+".csv"); h=p.read_text(encoding="utf8")
  ck(name,"dynamic-nav" in h and "enterprise_design_system" not in h and "--ds-primary" in h and "@media print" in h and "google" not in h.lower() and "/dashboard/undefined" not in h)
source=(S/"dashboard_dynamic.py").read_text(encoding="utf8"); ck("dynamic_navigation","DOMContentLoaded" in source and "querySelectorAll('main [id]')" in source); ck("no_fixed_industry_nav","<span>Ventas</span>" not in source and "PRIMOS & COUSINS" not in source)
from dashboard_dynamic import build_dashboard_plan
plan=build_dashboard_plan(pd.DataFrame([{"Contrato":"A","SLA":95,"Incidencias":2,"Tiempo":4}]),"comparar SLA e Incidencias","servicios.csv")
ck("structured_measures", isinstance(plan,dict))
print("PASS R10.20A.2")
