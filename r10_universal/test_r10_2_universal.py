from __future__ import annotations
import sys
from pathlib import Path
import pandas as pd

scripts = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent
sys.path.insert(0, str(scripts))
from universal_prompt_engine import compile_universal_plan, infer_semantic_roles, select_transactional_source
from enterprise_prompt_compiler import compile_enterprise_prompt


def must(cond, msg):
    if not cond:
        raise AssertionError(msg)

# 1) Ventas genericas: no requiere nombres de granos.
df = pd.DataFrame([
    {"Fecha":"2026-01-01","Cliente":"A","Producto":"X","Ventas":100.0,"Costo":70.0},
    {"Fecha":"2026-01-02","Cliente":"B","Producto":"Y","Ventas":200.0,"Costo":150.0},
])
p = compile_enterprise_prompt({}, df, "Analiza ventas, utilidad y margen por cliente y producto. Dashboard HTML.", "ventas.xlsx", "Datos")
must(p["prompt_compiler"]["mode"] == "universal-prompt-driven", "No activo compilador universal")
must(p["semantic_columns_strict"]["revenue"] == "Ventas", "No detecto ventas")
must(p["semantic_columns_strict"]["customer"] == "Cliente", "No detecto cliente")
must("ctrl_alm" not in str(p), "Se filtro hardcode legado ctrl_alm")

# 2) Inventario.
df2 = pd.DataFrame([{"SKU":"P1","Producto":"A","Existencia":20,"Almacen":"N"}])
p2 = compile_universal_plan(df2, "Analiza inventario por producto y almacen. Genera dashboard.")
must(p2["semantic_roles"]["stock"] == "Existencia", "No detecto existencia")
must(p2["semantic_roles"]["warehouse"] == "Almacen", "No detecto almacen")

# 3) RRHH.
df3 = pd.DataFrame([{"Empleado":"Ana","Departamento":"TI","Fecha":"2026-01-01","HorasExtra":2}])
r3 = infer_semantic_roles(df3)
must(r3["employee"] == "Empleado" and r3["department"] == "Departamento", "No detecto RRHH")

# 4) Cartera.
df4 = pd.DataFrame([{"Cliente":"A","Saldo":1000.0,"Fecha Vencimiento":"2026-01-01","Dias Vencidos":20}])
p4 = compile_universal_plan(df4, "Analiza cartera vencida, saldo por cliente y riesgo")
must(p4["semantic_roles"]["balance"] == "Saldo", "No detecto saldo")
must(p4["semantic_roles"]["due_date"] == "Fecha Vencimiento", "No detecto vencimiento")

# 5) Seleccion de fuente: detalle gana a resumen si no hay fuente explicita.
summary = pd.DataFrame([{"Mes":"2026-01","Ventas":300.0}])
detail = pd.DataFrame([
    {"Fecha":"2026-01-01","Factura":"F1","Cliente":"A","Producto":"X","Ventas":100.0},
    {"Fecha":"2026-01-02","Factura":"F2","Cliente":"B","Producto":"Y","Ventas":200.0},
])
sel = select_transactional_source({"Resumen":summary,"Movimientos":detail})
must(sel["sheet"] == "Movimientos", "No selecciono tabla transaccional")

print("PASS sales_generic")
print("PASS inventory_generic")
print("PASS hr_generic")
print("PASS receivables_generic")
print("PASS transactional_source_selection")
print("5/5 PASS R10.2 UNIVERSAL")
