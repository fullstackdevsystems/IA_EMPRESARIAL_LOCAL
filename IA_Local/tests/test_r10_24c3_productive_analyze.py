from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
UI = (ROOT / "IA_Local" / "scripts" / "enterprise_ai" / "product_workspaces_ui.py").read_text(encoding="utf8")
APP = (ROOT / "IA_Local" / "scripts" / "analizador_app.py").read_text(encoding="utf8")
UNIVERSAL = (ROOT / "IA_Local" / "scripts" / "analizador_universal.py").read_text(encoding="utf8")


def check(name: str, condition: bool) -> None:
    if not condition:
        raise AssertionError(name)
    print(f"PASS {name}")


check("professional_analyze_route", 'PRODUCT_ANALYZE_HTML=page("Analizar"' in UI)
check("real_multipart_upload", "form.append('file',file)" in UI and "pf('/api/analyze'" in UI)
check("missing_file_is_friendly", "Selecciona un archivo para comenzar." in UI)
check("missing_prompt_is_friendly", "Escribe qué quieres conocer" in UI)
check("result_uses_safe_text_content", "summary.textContent=txt(d.narrativa)" in UI)
check("deliverables_reused", "'/reports'" in UI and "Abrir panel" in UI and "Descargar PDF" in UI)
check("enterprise_auth_before_upload", "auth_actor = authorizer(authorization)" in APP)
check("analysis_scope_context", "ANALYZE_AUTH_CONTEXT.set(auth_actor)" in APP)
check("format_validation", 'if ext not in {".xlsx", ".xls", ".xlsb", ".xlsm", ".csv", ".txt"}' in APP)
check("registered_dataset_analysis_is_governed", "def analyze_registered_enterprise_dataset" in UNIVERSAL and "_authorize_analysis(authorization)" in UNIVERSAL)
check("dataset_cross_scope_returns_not_found", '"DATASET_NOT_FOUND"' in UNIVERSAL)
print("R10_24C3_PRODUCTIVE_ANALYZE=PASS")
