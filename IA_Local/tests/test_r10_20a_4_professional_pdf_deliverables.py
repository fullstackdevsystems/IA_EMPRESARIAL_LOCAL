from pathlib import Path
import sys
import tempfile

import fitz
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import reportes_profesionales as professional
from enterprise_design_system import DESIGN_SYSTEM_VERSION, get_pdf_design_tokens


def check(name, condition):
    if not condition:
        raise AssertionError(name)
    print("PASS", name)


def governed_manifest():
    return {
        "status": "READY",
        "source": {"filename": "source.csv", "sheet": "Datos", "row_count": 2, "source_fingerprint_sha256": "b" * 64},
        "components": [
            {"component_id": "kpi:advance", "title": "Avance físico", "status": "SUPPORTED", "value": 12, "unit": "count", "format": "integer", "provenance_source": "source"},
            {"component_id": "kpi:sla", "title": "SLA", "status": "DERIVABLE", "value": 0.25, "unit": "ratio", "format": "percentage", "provenance_source": "rule"},
            {"component_id": "kpi:cost", "title": "Costo", "status": "BLOCKED", "value": 123, "reason": "No hay regla aprobada", "provenance_source": "policy"},
            {"component_id": "kpi:estimate", "title": "Estimación", "status": "UNRESOLVED", "value": 456, "reason": "Evidencia insuficiente"},
            {"component_id": "kpi:conflict", "title": "Conflicto", "status": "CONFLICT", "value": 789, "reason": "Fuentes incompatibles"},
        ],
    }


def profile(domain, rows):
    return {"archivo": f"{domain}.csv", "filas": len(rows), "columnas": list(rows.columns), "run_id": "run-r10-20a-4", "roles_detectados": {}, "deliverable_manifest": governed_manifest(), "periodo": {"desde": "2026-01-01", "hasta": "2026-12-31"}}


def sections(rows):
    return {"KPIs_Generales": pd.DataFrame([["Filas", len(rows)], ["Columnas", len(rows.columns)]], columns=["Indicador", "Valor"]), "Resultado": rows}


print("=== R10.20A.4 PROFESSIONAL PDF DELIVERABLES ===")
check("canonical_generator", callable(professional.pdf_report_professional))
check("pdf_design_system", get_pdf_design_tokens()["version"] == DESIGN_SYSTEM_VERSION)

fixtures = {
    "construccion": pd.DataFrame({"Proyecto": ["P-01", "P-02"], "Avance físico": [0.25, 0.5], "Presupuesto": [1000.5, 2000.75], "Estatus": ["Activo", "En revisión"]}),
    "servicios": pd.DataFrame({"Contrato": ["C-01", "C-02"], "SLA": [0.95, 0.9], "Incidencias": [2, 3], "Tiempo atención": [1.25, 2.5]}),
    "logistica": pd.DataFrame({"Ruta": ["R-01", "R-02"], "Unidad operativa": ["U-1", "U-2"], "Carga": [10, 20], "Estado": ["Completa", "En tránsito"]}),
}

with tempfile.TemporaryDirectory() as td:
    for domain, rows in fixtures.items():
        root = Path(td)
        pdf_path = root / f"{domain}.pdf"
        xlsx_path = root / f"{domain}.xlsx"
        data_profile = profile(domain, rows)
        data_sections = sections(rows)
        professional.pdf_report_professional(pdf_path, "Consulta UTF-8: año, construcción y atención", data_profile, data_sections, [], "", "general")
        professional.excel_report_professional(xlsx_path, "Consulta UTF-8", data_profile, {"type": "overview"}, data_sections, [], "", rows, rows, {}, "general")
        check(f"pdf_created_{domain}", pdf_path.is_file() and pdf_path.read_bytes().startswith(b"%PDF"))
        document = fitz.open(pdf_path)
        text = "\n".join(page.get_text() for page in document)
        check(f"pdf_valid_{domain}", document.page_count >= 2 and "IA Empresarial Local" in text and DESIGN_SYSTEM_VERSION in text)
        check(f"cover_and_footer_{domain}", "Fuente:" in text and "Página 1" in text and "Información del análisis" in text)
        check(f"statuses_{domain}", all(status in text for status in ("SUPPORTED", "DERIVABLE", "BLOCKED", "UNRESOLVED", "CONFLICT")))
        check(f"blocked_reason_{domain}", "No hay regla aprobada" in text and "123" not in text)
        check(f"provenance_utf8_{domain}", "b" * 64 in text and "Avance físico" in text)
        check(f"no_secrets_{domain}", "password" not in text.lower() and "connection string" not in text.lower())
        check(f"professional_structure_{domain}", "Indicadores gobernados" in text and "Hallazgos ejecutivos" in text and "Gobernanza y trazabilidad" in text)
        document.close()
        import openpyxl
        workbook = openpyxl.load_workbook(xlsx_path, data_only=False)
        excel_values = [cell.value for row in workbook["Resumen"].iter_rows() for cell in row]
        check(f"cross_output_{domain}", "kpi:advance" in excel_values and 12 in excel_values and "kpi:advance" in text and "12" in text)
        workbook.close()

print("PASS R10.20A.4 PROFESSIONAL PDF DELIVERABLES")
