from pathlib import Path
import ast, importlib.util
ROOT=Path(__file__).resolve().parents[2]
api_path=ROOT/"IA_Local"/"scripts"/"enterprise_ai"/"api.py"
ui_path=ROOT/"IA_Local"/"scripts"/"enterprise_ai"/"product_workspaces_ui.py"
api=api_path.read_text(encoding="utf-8"); ui=ui_path.read_text(encoding="utf-8")
ast.parse(api); ast.parse(ui)
spec=importlib.util.spec_from_file_location("r10_24a3_ui",ui_path)
module=importlib.util.module_from_spec(spec); assert spec.loader is not None; spec.loader.exec_module(module)
pages={"/analyze":module.PRODUCT_ANALYZE_HTML,"/data":module.PRODUCT_DATA_HTML,"/reports":module.PRODUCT_REPORTS_HTML}
for html in pages.values():
    assert len(html)>8500
    for marker in ["IA Empresarial Local","/app","/assistant","/analyze","/data","/reports","/settings","/api/auth/login","/api/auth/logout","/api/enterprise/app-context","@media(max-width:820px)"]: assert marker in html
for marker in ["Convierte tus datos en decisiones","Nuevo análisis","Analizar archivo","Qué obtendrás","/api/analyze"]: assert marker in pages["/analyze"]
for marker in ["La información de tu empresa, en un solo lugar","Información disponible","Agregar información","Conexiones empresariales","/api/enterprise/documents","/api/enterprise/datasets","/api/enterprise/control-plane/sql-sources"]: assert marker in pages["/data"]
for marker in ["Tus resultados, organizados y disponibles","Resultados generados","Nuevo análisis","/api/deliverables"]: assert marker in pages["/reports"]
for forbidden in ["Open WebUI","R10.13","Verified Prompt","ODBC Driver","qdrant","Python/Pandas","127.0.0.1","localhost"]: assert forbidden not in ui
for route,constant in [("/analyze","PRODUCT_ANALYZE_HTML"),("/data","PRODUCT_DATA_HTML"),("/reports","PRODUCT_REPORTS_HTML")]:
    start=api.index(f'@router.get("{route}"'); end=api.find("\n    @router.",start+1); block=api[start:] if end<0 else api[start:end]
    assert constant in block and "HTMLResponse" in block and "RedirectResponse" not in block
for marker in ['@router.post("/api/enterprise/documents")','@router.get("/api/enterprise/documents")','@router.get("/api/enterprise/datasets")']: assert marker in api
universal=(ROOT/"IA_Local"/"scripts"/"analizador_universal.py").read_text(encoding="utf-8")
analyzer=(ROOT/"IA_Local"/"scripts"/"analizador_app.py").read_text(encoding="utf-8")
for marker in ["/api/enterprise/datasets/{dataset_id}/analyze","/api/deliverables","/api/deliverables/{run_id}/download/{kind}","/api/sql/connections","/api/sql/query-safe"]: assert marker in universal
assert "/api/analyze" in analyzer
print("R10_24A3_CONTRACT=PASS")
print("ANALYZE_SURFACE=PASS")
print("DATA_SURFACE=PASS")
print("REPORTS_SURFACE=PASS")
print("TECHNICAL_COPY_HIDDEN=PASS")
print("LEGACY_BACKEND_CAPABILITIES_PRESERVED=YES")
print("RESPONSIVE_CONTRACT=PASS")

assert "/api/enterprise/control-plane/sql-sources" in api
