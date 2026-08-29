from __future__ import annotations
import tempfile
from pathlib import Path
import pandas as pd
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from performance import execution_plan, execute_csv_chunked_exact, can_stream_exact, optional_engines


def check(name, cond):
    if not cond: raise AssertionError(name)
    print("PASS", name)

with tempfile.TemporaryDirectory() as td:
    p = Path(td) / "ventas.csv"
    rows = 120_000
    df = pd.DataFrame({
        "Fecha": ["2025-01-01"] * 60_000 + ["2026-01-01"] * 60_000,
        "Producto": ["A", "B"] * 60_000,
        "Cantidad": [2] * rows,
        "Precio": [10.0] * rows,
        "Venta": [20.0] * rows,
    })
    df.to_csv(p, index=False)
    dataset={"path":str(p),"name":"ventas.csv","columns":list(df.columns),"roles":{"date":"Fecha","product":"Producto","quantity":"Cantidad","price":"Precio","sales":"Venta"}}
    plan={"operation":"sum","metric":"sales","group_by":None,"year":2025,"filters":[]}
    r=execute_csv_chunked_exact(dataset,plan,chunk_rows=25_000)
    check("exact_sum", r["value"] == 1_200_000.0)
    check("chunked_multiple", r["source"]["chunks"] > 1)
    check("no_metric_sampling", r["source"]["sampled_for_metric"] is False and r["source"]["exact"] is True)
    plan2={"operation":"top","metric":"sales","group_by":"product","year":2026,"filters":[]}
    r2=execute_csv_chunked_exact(dataset,plan2,chunk_rows=30_000)
    check("grouped_exact", len(r2["value"]) == 2 and sum(x["value"] for x in r2["value"]) == 1_200_000.0)
    ok,reason=can_stream_exact(dataset,plan,large_mb=0)
    check("eligible_large_csv", ok and reason=="ok")
    ok2,reason2=can_stream_exact(dataset,{**plan,"metric":"profit"},large_mb=0)
    check("profit_fallback", (not ok2) and "profit" in reason2)
    check("engine_inventory", optional_engines().get("pandas") is True)
    ep=execution_plan(p,large_mb=0)
    check("execution_policy_exact", ep["metrics_exact"] is True and ep["large"] is True)
print("8/8 PASS R10.11 PERFORMANCE")
