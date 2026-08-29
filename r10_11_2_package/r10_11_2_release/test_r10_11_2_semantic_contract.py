from pathlib import Path
import sys, types
import pandas as pd

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))

stub=types.ModuleType("semantic_layer")
def resolve_semantic_map(df):
    return {"usable":{
        "date":"Fecha","week":"Semana","customer":"Cliente","customer_id":"Cod_Cliente",
        "product":"Articulo","product_group":"ctrl_alm","category":"Categoria","seller":"Vendedor",
        "zone":"Zona","line":"cod_linea","reference":"Refer","revenue":"Importe_Venta",
        "quantity":"Toneladas_Vendidas","cost":"Costo","profit":"Utilidad","freight":"Costo_Flete",
        "product_cost":"Costo_Producto","other_cost":"Otros_Costos","shrinkage":"Toneladas_Mermadas",
        "supplier":"Proveedor","warehouse":"Almacen","origin_city":"Ciudad_Origen","destination_city":"Ciudad_Destino"
    }}
stub.resolve_semantic_map=resolve_semantic_map
sys.modules["semantic_layer"]=stub

from semantic_contract_enforcer import enforce_semantic_contract

df=pd.DataFrame({
 "Fecha":["2026-08-01"],"Semana":["Semana 1-8"],"Zona":["OCCIDENTE"],"Categoria":["CALL CENTER"],
 "Vendedor":["A"],"Cliente":["C"],"Cod_Cliente":["001"],"Articulo":["MAIZ"],"ctrl_alm":["MAIZ AMARILLO GRANEL"],
 "Proveedor":["P"],"Almacen":["ALM"],"Ciudad_Origen":["CULIACAN"],"Ciudad_Destino":["MAZATLAN"],"Cliente_Recoge":["N"],
 "Refer":["R1"],"Toneladas_Vendidas":[10.0],"Toneladas_Costo":[20.0],"Importe_Venta":[1000.0],
 "Costo":[900.0],"Utilidad":[100.0],"Costo_Producto":[700.0],"Costo_Flete":[150.0],
 "Otros_Costos":[50.0],"Toneladas_Mermadas":[0.1],"cod_linea":["GRANO"]
})
plan={"semantic_roles":{"quantity":"Toneladas_Costo"},"charts":[{"type":"line","title":"Evolución de Cantidad / Volumen","measure":"Toneladas_Costo","dimension":"Fecha","op":"sum"}],"warnings":[]}
prompt="DASHBOARD. KPIs EJECUTIVOS: TONELADAS VENDIDAS, UTILIDAD POR TONELADA. FILTROS GLOBALES: Fecha desde, Fecha hasta, Semana, ctrl_alm, Cliente_Recoge."
out=enforce_semantic_contract(plan,df,prompt)
assert out["semantic_roles"]["quantity"]=="Toneladas_Vendidas"
assert next(k for k in out["kpis"] if k["key"]=="quantity")["column"]=="Toneladas_Vendidas"
assert next(k for k in out["kpis"] if k["key"]=="profit_per_unit")["denominator"]=="Toneladas_Vendidas"
assert out["charts"][0]["measure"]=="Toneladas_Vendidas"
cols={x["column"] for x in out["filters"]}
for req in ["Semana","ctrl_alm","Ciudad_Origen","Ciudad_Destino","Cliente_Recoge"]:
    assert req in cols,req
print("PASS strict_quantity")
print("PASS profit_per_ton")
print("PASS strict_chart_measure")
print("PASS mandated_filters")
print("4/4 PASS R10.11.2 SEMANTIC CONTRACT")
