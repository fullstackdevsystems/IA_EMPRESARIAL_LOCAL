from pathlib import Path

root = Path(__file__).resolve().parents[2]
ui = (root / "IA_Local/scripts/enterprise_ai/product_workspaces_ui.py").read_text(encoding="utf8")
host = (root / "IA_Local/scripts/analizador_universal.py").read_text(encoding="utf8")

def check(name, value):
    assert value, name
    print(f"PASS {name}")

check("analysis_reuses_governed_endpoint", "pf('/api/analyze'" in ui)
check("business_narrative_visible", "summary.textContent=txt(d.narrativa)" in ui)
check("dashboard_reused", "Abrir panel" in ui and "/dashboard/" in ui)
check("pdf_reused", "Descargar PDF" in ui)
check("excel_reused", "Descargar Excel" in ui)
check("reports_history_reused", "Ver todos los reportes" in ui and "'/api/deliverables'" in ui)
check("dataset_analysis_governed", "analyze_registered_enterprise_dataset" in host)
print("R10_26C_FINDING_TO_DECISION=PASS")
