from pathlib import Path
import json
import sys
import tempfile

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import analizador_universal as analyzer
from enterprise_deliverable_manifest import build_governed_deliverable_manifest
from enterprise_deliverable_registry import GovernedDeliverableRegistry
from enterprise_knowledge_qa import answer_unified_enterprise_question
from enterprise_knowledge_store import EnterpriseKnowledgeError, EnterpriseKnowledgeStore


SCOPE_A = {"company_id": "empresa-a", "user_id": "ana", "business_unit": None, "branch": None}
SCOPE_B = {"company_id": "empresa-b", "user_id": "ana", "business_unit": None, "branch": None}


def check(name, condition):
    if not condition:
        raise AssertionError(name)
    print("PASS", name)


def blocked(name, code, action):
    try:
        action()
    except EnterpriseKnowledgeError as exc:
        check(name, exc.code == code)
        return
    raise AssertionError(name)


def add(store, scope, knowledge_id, title, content):
    return store.register_knowledge(
        scope=scope, knowledge_id=knowledge_id, knowledge_type="business_term",
        title=title, content=content, source={"source": "documento-validado", "document_id": "doc-1"},
        provenance={"origin": "authorized_user", "approved_by": "ana"}, confidence=0.9,
        tags=["definición", "empresa"],
    )


def register_run(reports, scope):
    spec = {"schema_version": "r10.13a", "source": {"fingerprint_sha256": "b" * 64}, "components": [{"id": "kpi:freight", "type": "kpi", "status": "BLOCKED", "reason": "approved_rule_required"}]}
    plan = {"execution_plan": {"version": "r10.11.3", "dashboard_spec": spec}}
    manifest = build_governed_deliverable_manifest(dashboard_plan=plan, filename="source.csv")
    html = reports / "dashboard.html"
    html.write_text("<script>const DATA=" + json.dumps({"plan": {"execution_plan": {"dashboard_spec": spec}}}) + ";</script>", encoding="utf-8")
    return GovernedDeliverableRegistry(reports).register(scope=scope, run_id="run-current", manifest=manifest, outputs={"html": html.name})


print("\n=== R10.19B UNIFIED ENTERPRISE KNOWLEDGE Q&A ===")
with tempfile.TemporaryDirectory() as td:
    reports = Path(td) / "Reportes"
    reports.mkdir()
    store = EnterpriseKnowledgeStore(reports / ".knowledge")
    record = add(store, SCOPE_A, "term-abc", "ABC", "ABC significa Área de Beneficio Corporativo.")
    check("register_valid_record", record["status"] == "ACTIVE" and record["knowledge_type"] == "business_term")
    check("fingerprint_integrity", len(record["fingerprint_sha256"]) == 64)
    check("get_by_id", store.get(SCOPE_A, "term-abc")["content"] == record["content"])
    check("same_scope_search_utf8", [item["knowledge_id"] for item in store.search(SCOPE_A, "¿Qué significa ABC?")] == ["term-abc"])
    blocked("cross_tenant_get_blocked", "KNOWLEDGE_NOT_FOUND", lambda: store.get(SCOPE_B, "term-abc"))
    check("cross_tenant_search_no_leakage", store.search(SCOPE_B, "ABC") == [])
    restarted = EnterpriseKnowledgeStore(reports / ".knowledge")
    check("persistent_restart", restarted.get(SCOPE_A, "term-abc")["fingerprint_sha256"] == record["fingerprint_sha256"])

    registry = GovernedDeliverableRegistry(reports)
    answered = answer_unified_enterprise_question(registry=registry, knowledge_store=store, scope=SCOPE_A, question="¿Qué significa ABC?")
    check("knowledge_qa_answered", answered["status"] == "ANSWERED" and answered["answer"] == record["content"])
    check("provenance_included", answered["provenance"]["origin"] == "authorized_user" and answered["knowledge_ids"] == ["term-abc"])
    other_tenant = answer_unified_enterprise_question(registry=registry, knowledge_store=store, scope=SCOPE_B, question="¿Qué significa ABC?")
    check("cross_tenant_qa_unresolved", other_tenant["status"] == "UNRESOLVED" and other_tenant["answer"] is None)
    unresolved = answer_unified_enterprise_question(registry=registry, knowledge_store=store, scope=SCOPE_A, question="¿Qué significa XYZ?")
    check("knowledge_absent_unresolved", unresolved["status"] == "UNRESOLVED" and unresolved["answer"] is None)
    check("knowledge_does_not_create_formula", "formula" not in answered and answered["governance"]["llm_formula_authority"] is False)

    invalidated = store.invalidate(SCOPE_A, "term-abc", reason="definition retired", actor="ana")
    check("invalidation_versioned", invalidated["status"] == "INVALIDATED" and invalidated["version"] == 2)
    after_invalidation = answer_unified_enterprise_question(registry=registry, knowledge_store=store, scope=SCOPE_A, question="ABC")
    check("invalidated_not_usable", after_invalidation["status"] == "UNRESOLVED")

    add(store, SCOPE_A, "term-abc-v2", "ABC", "ABC significa Área de Beneficio Corporativo vigente.")
    add(store, SCOPE_A, "term-abc-alt", "ABC", "ABC significa Acuerdo Base de Control.")
    conflict = answer_unified_enterprise_question(registry=registry, knowledge_store=store, scope=SCOPE_A, question="ABC")
    check("conflict_fail_closed", conflict["status"] == "CONFLICT" and conflict["answer"] is None and len(conflict["knowledge_ids"]) == 2)

    run = register_run(reports, SCOPE_A)
    current = answer_unified_enterprise_question(registry=registry, knowledge_store=store, scope=SCOPE_A, run_id=run["run_id"], question="¿Cuál es el flete?")
    check("current_analytical_r10_19a_precedence", current["status"] == "BLOCKED" and current["answer"] is None and current["evidence_source"] == "current_governed_run")

    old_reports = analyzer.base.REPORTES
    analyzer.base.REPORTES = reports
    try:
        local_store = EnterpriseKnowledgeStore(reports / ".knowledge")
        add(local_store, analyzer._local_deliverable_scope(), "medical-term", "Convenio Premium", "Convenio Premium usa tabulador X.")
        with TestClient(analyzer.app) as client:
            response = client.post("/api/ask", json={"question": "¿Qué es Convenio Premium?"})
            check("api_ask_compatible", response.status_code == 200 and response.json()["result"]["status"] == "ANSWERED")
    finally:
        analyzer.base.REPORTES = old_reports

    tamper = add(store, SCOPE_A, "tamper-record", "Término verificable", "Contenido gobernado.")
    tamper_path = store._path(SCOPE_A, tamper["knowledge_id"])
    tamper_path.write_text(tamper_path.read_text(encoding="utf-8").replace("Contenido gobernado.", "Contenido alterado."), encoding="utf-8")
    blocked("tampered_record_fail_closed", "KNOWLEDGE_INTEGRITY_MISMATCH", lambda: store.get(SCOPE_A, "tamper-record"))

print("PASS R10.19B UNIFIED ENTERPRISE KNOWLEDGE Q&A")
