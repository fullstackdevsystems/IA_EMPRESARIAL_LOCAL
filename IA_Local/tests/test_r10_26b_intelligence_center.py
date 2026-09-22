from pathlib import Path

root = Path(__file__).resolve().parents[2]
ui = (root / "IA_Local/scripts/enterprise_ai/product_assistant_ui.py").read_text(encoding="utf8")
service = (root / "IA_Local/scripts/enterprise_ai/service.py").read_text(encoding="utf8")

def check(name, value):
    assert value, name
    print(f"PASS {name}")

check("assistant_reused", "/api/enterprise/chat/stream" in ui)
check("governed_fact_label", "Hecho calculado · basado en información verificada" in ui)
check("interpretation_label", "Interpretación asistida · revisa las fuentes indicadas" in ui)
check("structured_route_distinguished", "retrieval.structured || retrieval.fast_path === 'governed_sql'" in ui)
check("sources_remain_visible", "renderSourceSummary(event)" in ui)
check("deterministic_authority_preserved", "deterministic_evidence_authority_preserved" in service)
check("governed_sql_preserved", 'route == "governed_sql"' in service)
print("R10_26B_INTELLIGENCE_CENTER=PASS")
