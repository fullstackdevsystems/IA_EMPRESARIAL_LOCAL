from __future__ import annotations

"""Prueba rapida de regresion V7 (no requiere Ollama ni archivos externos)."""

import os
from pathlib import Path
import tempfile
import pandas as pd

import analizador_universal as au


def main() -> int:
    rows=[]
    for y in (2025, 2026):
        months=range(1,13) if y==2025 else range(1,9)
        for m in months:
            for i in range(5):
                rows.append({
                    "Invoice":f"{y}{m:02d}{i:03d}",
                    "StockCode":f"SKU{i%3}",
                    "Description":["Melaza","Maiz","Pasta"][i%3],
                    "Quantity":10+i,
                    "InvoiceDate":f"{y}-{m:02d}-15",
                    "Price":100+i*5,
                    "Customer ID":1000+i%4,
                    "Country":"Mexico" if i<4 else "USA",
                })
    df=pd.DataFrame(rows)
    h=au.base.heuristic_plan("Analiza completamente el archivo. No inventes formulas respaldadas por los datos.")
    assert au._is_broad_overview_request("Analiza completamente el archivo. No inventes formulas respaldadas por los datos.",h)
    fake={"operation":"describe","filters":[{"column":"Invoice","op":"contains","value":"202501000"}]}
    valid=au._validate_generic_plan(fake,"Describe el archivo",df)
    assert valid is not None and valid.get("filters")==[], valid
    roles=au.infer_roles(df)
    work,derived=au.base.prepare_df(df,roles)
    profile=au.build_profile(work,df,roles,derived,{"archivo":"regresion.csv"})
    assert profile["calidad_archivo"]["filas"]==len(df)
    assert profile["calidad_archivo"]["columnas"]==8
    print("OK V7: overview protegido, filtros alucinados bloqueados y calidad sobre archivo completo.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
