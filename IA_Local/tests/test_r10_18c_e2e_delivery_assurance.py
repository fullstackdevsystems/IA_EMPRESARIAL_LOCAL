from pathlib import Path
import os
import sys
import tempfile

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import analizador_universal as analyzer
from enterprise_deliverable_registry import GovernedDeliverableRegistry


def check(name, condition):
    if not condition:
        print("FAIL", name)
        raise AssertionError(name)
    print("PASS", name)


prompt = """Genera dashboard HTML, PDF y Excel con ventas, costo, utilidad y flete.
No calcules flete sin una regla aprobada. Incluye trazabilidad y capacidades bloqueadas."""

print("\n=== R10.18C E2E DELIVERY ASSURANCE ===")
with tempfile.TemporaryDirectory() as td:
    root = Path(td)
    source = root / "ventas.csv"
    pd.DataFrame([
        {"Fecha":"2026-01-10", "Cliente":"A", "Articulo":"P1", "Importe_Venta":1000, "Costo":800, "Toneladas_Vendidas":10, "Costo_Flete_Corto":10},
        {"Fecha":"2026-02-10", "Cliente":"B", "Articulo":"P2", "Importe_Venta":2400, "Costo":1800, "Toneladas_Vendidas":20, "Costo_Flete_Largo":30},
    ]).to_csv(source, index=False)
    reports = root / "Reportes"
    reports.mkdir()
    old_reports = analyzer.base.REPORTES
    old_llm = os.environ.get("IA_DYNAMIC_DASHBOARD_LLM")
    analyzer.base.REPORTES = reports
    os.environ["IA_DYNAMIC_DASHBOARD_LLM"] = "0"
    try:
        result = analyzer.analyze_file(source, prompt)
        contract = result["output_contract"]
        check("analysis_ok", result["ok"] is True)
        check("contract_complete", contract["schema_version"] == "r10.18c" and contract["status"] == "COMPLETE")
        check("three_generated", all(contract["formats"][kind]["status"] == "GENERATED" for kind in ("html", "pdf", "excel")))
        check("three_files", all((reports / result[kind]).is_file() for kind in ("html", "pdf", "excel")))
        run = result["deliverable_run"]
        check("registry_contract_chain", run["output_contract_fingerprint_sha256"] == contract["contract_fingerprint_sha256"])
        restarted = GovernedDeliverableRegistry(reports)
        loaded = restarted.get(analyzer._local_deliverable_scope(), run["run_id"])
        check("restart_contract_chain", loaded["output_contract_fingerprint_sha256"] == contract["contract_fingerprint_sha256"])
        html = (reports / result["html"]).read_text(encoding="utf-8", errors="replace")
        check("freight_blocked", '"id":"kpi:freight"' in html and '"status":"BLOCKED"' in html)
    finally:
        analyzer.base.REPORTES = old_reports
        if old_llm is None:
            os.environ.pop("IA_DYNAMIC_DASHBOARD_LLM", None)
        else:
            os.environ["IA_DYNAMIC_DASHBOARD_LLM"] = old_llm

print("PASS R10.18C E2E DELIVERY ASSURANCE")
