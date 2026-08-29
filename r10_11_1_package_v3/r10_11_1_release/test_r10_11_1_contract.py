from pathlib import Path
import sys, tempfile
import pandas as pd
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from data_contract import extract_explicit_sheet, validate_workbook_contract, DataContractError

PROMPT='''FUENTE ÚNICA DE VERDAD
La hoja:

BD

es la BASE DE DATOS PRINCIPAL y la ÚNICA FUENTE DE VERDAD.

COLUMNAS DE BD
==============
Fecha
Utilidad
Costo_Flete
ctrl_alm

==================================================
PASO 1 — VALIDACIÓN
'''
assert extract_explicit_sheet(PROMPT)=="BD"
with tempfile.TemporaryDirectory() as td:
    good=Path(td)/"good.xlsx"
    bad=Path(td)/"bad.xlsx"
    pd.DataFrame({"Fecha":["2026-08-01"],"Utilidad":[10.0],"Costo_Flete":[2.0],"ctrl_alm":["SORGO"]}).to_excel(good,sheet_name="BD",index=False)
    pd.DataFrame({"Fecha":["2026-08-01"]}).to_excel(bad,sheet_name="Datos",index=False)
    ok=validate_workbook_contract(good,PROMPT)
    assert ok["ok"] and ok["explicit_sheet"]=="BD" and not ok["missing_columns"]
    print("PASS valid_contract")
    try:
        validate_workbook_contract(bad,PROMPT)
        raise AssertionError("expected contract error")
    except DataContractError as e:
        assert e.code=="SOURCE_SHEET_NOT_FOUND"
        print("PASS missing_source_controlled")
print("2/2 PASS R10.11.1 CONTRACT")
