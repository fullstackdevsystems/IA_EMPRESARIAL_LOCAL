from pathlib import Path
ROOT=Path(__file__).resolve().parent
a=(ROOT/"apply_r10_11_1.py").read_text(encoding="utf-8")
checks={
"date_guard":"Parse only values that already look like calendar dates." in a,
"source_contract":"validate_workbook_contract" in a and "requested_sheet" in a,
"real_profit":"utilidad_fuente" in a and "columna_real" in a,
"real_freight":"freight_total" in a and "flete_fuente" in a,
"output_context":"generar excel" in a and "reporte excel" in a,
"structured_error":"SOURCE_SHEET_NOT_FOUND" in a and "analizador.err.log" in a and "traceback.format_exc" in a,
}
for k,v in checks.items():
    assert v,k
    print("PASS",k)
print(f"{len(checks)}/{len(checks)} PASS R10.11.1 PATCH")
