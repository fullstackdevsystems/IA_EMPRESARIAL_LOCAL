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
from enterprise_deliverable_registry import (
    DeliverableRegistryError,
    GovernedDeliverableRegistry,
)
from enterprise_question_answering import answer_enterprise_question


SCOPE = {"company_id": "empresa-a", "user_id": "ana", "business_unit": None, "branch": None}
OTHER_SCOPE = {"company_id": "empresa-b", "user_id": "ana", "business_unit": None, "branch": None}


def check(name, condition):
    if not condition:
        raise AssertionError(name)
    print("PASS", name)


def expect_error(name, code, action):
    try:
        action()
    except (ValueError, DeliverableRegistryError) as exc:
        check(name, str(exc) == code or getattr(exc, "code", None) == code)
        return
    raise AssertionError(name)


def spec(components=None):
    return {
        "schema_version": "r10.13a",
        "source": {"fingerprint_sha256": "b" * 64},
        "coverage": {"requested": 3, "supported": 1, "derivable": 1, "blocked": 1, "fulfilled": 2, "percent": 66.67},
        "components": components or [
            {"id": "kpi:revenue", "type": "kpi", "status": "SUPPORTED", "value": 1234.5},
            {"id": "kpi:freight", "type": "kpi", "status": "BLOCKED", "reason": "approved_business_rule_required"},
        ],
    }


def register(reports, run_id, *, html=None, components=None, outputs=None, scope=SCOPE):
    plan = {
        "request_prompt_sha256": "a" * 64,
        "prompt_integrity": "r10.19a-test",
        "execution_plan": {"version": "r10.11.3", "dashboard_spec": spec(components)},
    }
    manifest = build_governed_deliverable_manifest(
        dashboard_plan=plan, filename="ventas.csv", output_intent={"outputs": {"html": bool(html), "excel": bool(outputs and outputs.get("excel")), "pdf": bool(outputs and outputs.get("pdf"))}},
    )
    html_name = f"dashboard_{run_id}.html"
    if html is not None:
        (reports / html_name).write_text(html, encoding="utf-8")
    output_names = dict(outputs or {})
    if html is not None:
        output_names["html"] = html_name
    return GovernedDeliverableRegistry(reports).register(
        scope=scope, run_id=run_id, manifest=manifest, outputs=output_names,
    )


def dashboard_html(payload):
    return "<script>const DATA=" + json.dumps(payload, ensure_ascii=False) + ";</script>"


print("\n=== R10.19A GOVERNED ENTERPRISE QUESTION ANSWERING ===")
with tempfile.TemporaryDirectory() as td:
    reports = Path(td) / "Reportes"
    reports.mkdir()
    payload = {"plan": {"execution_plan": {"dashboard_spec": spec()}}}
    register(reports, "run-main", html=dashboard_html(payload))
    registry = GovernedDeliverableRegistry(reports)

    expect_error("question_required", "QUESTION_REQUIRED", lambda: answer_enterprise_question(registry=registry, scope=SCOPE, run_id="run-main", question=""))
    expect_error("nonexistent_run_fail_closed", "RUN_NOT_FOUND", lambda: answer_enterprise_question(registry=registry, scope=SCOPE, run_id="run-none", question="formatos"))
    expect_error("wrong_scope_fail_closed", "RUN_NOT_FOUND", lambda: answer_enterprise_question(registry=registry, scope=OTHER_SCOPE, run_id="run-main", question="formatos"))

    formats = answer_enterprise_question(registry=registry, scope=SCOPE, run_id="run-main", question="¿Qué entregables existen?")
    check("deliverables_registry_only_answered", formats["status"] == "ANSWERED" and formats["answer"]["formats"] == ["html"])
    source = answer_enterprise_question(registry=registry, scope=SCOPE, run_id="run-main", question="¿Cuál es la fuente?")
    check("source_registry_only_answered_utf8", source["status"] == "ANSWERED" and source["answer"]["source_fingerprint_sha256"] == "b" * 64)

    (reports / "only.xlsx").write_bytes(b"xlsx")
    register(reports, "run-no-html", outputs={"excel": "only.xlsx"})
    no_html = answer_enterprise_question(registry=registry, scope=SCOPE, run_id="run-no-html", question="formatos generados")
    check("registry_only_does_not_parse_html", no_html["status"] == "ANSWERED" and no_html["answer"]["formats"] == ["excel"])
    expect_error("analytical_without_html_fail_closed", "HTML_DELIVERABLE_REQUIRED", lambda: answer_enterprise_question(registry=registry, scope=SCOPE, run_id="run-no-html", question="cobertura"))

    coverage = answer_enterprise_question(registry=registry, scope=SCOPE, run_id="run-main", question="cobertura")
    check("coverage_answered_canonical_path", coverage["status"] == "ANSWERED" and coverage["answer"]["percent"] == 66.67)
    check("governance_flags", coverage["governance"]["fail_closed"] is True and coverage["governance"]["llm_computational_authority"] is False and coverage["governance"]["llm_formula_authority"] is False)
    blocked = answer_enterprise_question(registry=registry, scope=SCOPE, run_id="run-main", question="capacidades bloqueadas")
    check("blocked_capabilities", blocked["status"] == "ANSWERED" and blocked["answer"][0]["id"] == "kpi:freight")
    freight = answer_enterprise_question(registry=registry, scope=SCOPE, run_id="run-main", question="¿Cuál es el flete?")
    check("freight_blocked_null", freight["status"] == "BLOCKED" and freight["answer"] is None)
    unknown = answer_enterprise_question(registry=registry, scope=SCOPE, run_id="run-main", question="¿Cuál es el indicador futuro?")
    check("unknown_unresolved", unknown["status"] == "UNRESOLVED" and unknown["answer"] is None)
    missing_component = answer_enterprise_question(registry=registry, scope=SCOPE, run_id="run-main", question="clientes activos")
    check("missing_component_unresolved", missing_component["status"] == "UNRESOLVED" and missing_component["reason"] == "component_not_present_in_governed_spec")
    revenue = answer_enterprise_question(registry=registry, scope=SCOPE, run_id="run-main", question="ventas totales")
    check("persisted_metric_answered", revenue["status"] == "ANSWERED" and revenue["answer"]["value"] == 1234.5)

    missing_payload = {"plan": {"execution_plan": {"dashboard_spec": spec([{ "id": "kpi:revenue", "type": "kpi", "status": "SUPPORTED" }])}}}
    register(reports, "run-missing", html=dashboard_html(missing_payload), components=[{ "id": "kpi:revenue", "type": "kpi", "status": "SUPPORTED" }])
    missing = answer_enterprise_question(registry=registry, scope=SCOPE, run_id="run-missing", question="ventas")
    check("missing_persisted_value_unresolved", missing["status"] == "UNRESOLVED" and missing["reason"] == "governed_component_has_no_persisted_value")

    invalid_payload = {"plan": {"execution_plan": {"dashboard_spec": spec([{ "id": "kpi:revenue", "type": "kpi", "status": "FUTURE" }])}}}
    register(reports, "run-invalid", html=dashboard_html(invalid_payload), components=[{ "id": "kpi:revenue", "type": "kpi", "status": "FUTURE" }])
    invalid = answer_enterprise_question(registry=registry, scope=SCOPE, run_id="run-invalid", question="ventas")
    check("invalid_component_status_unresolved", invalid["status"] == "UNRESOLVED" and invalid["answer"] is None)

    register(reports, "run-malformed", html="<html>sin payload</html>")
    expect_error("malformed_analytical_html_fail_closed", "DASHBOARD_PAYLOAD_MARKER_NOT_FOUND: no se encontró la asignación DATA en el HTML", lambda: answer_enterprise_question(registry=registry, scope=SCOPE, run_id="run-malformed", question="cobertura"))

    old_reports = analyzer.base.REPORTES
    analyzer.base.REPORTES = reports
    try:
        register(
            reports,
            "run-main",
            html=dashboard_html(payload),
            scope=analyzer._local_deliverable_scope(),
        )
        with TestClient(analyzer.app) as client:
            api = client.post("/api/ask", json={"run_id": "run-main", "question": "¿Qué formatos generó?"})
            check("api_ask", api.status_code == 200 and api.json()["result"]["status"] == "ANSWERED")
            page = client.get("/")
            check("dashboard_html_compatibility", b"const dashboardFile=d.dashboard||d.html||null;" in page.content and b"/dashboard/undefined" not in page.content)
    finally:
        analyzer.base.REPORTES = old_reports

    (reports / "dashboard_run-main.html").write_text("tampered", encoding="utf-8")
    expect_error("tampered_artifact_fail_closed", "ARTIFACT_INTEGRITY_MISMATCH", lambda: answer_enterprise_question(registry=registry, scope=SCOPE, run_id="run-main", question="formatos"))

print("PASS R10.19A GOVERNED ENTERPRISE QUESTION ANSWERING")
