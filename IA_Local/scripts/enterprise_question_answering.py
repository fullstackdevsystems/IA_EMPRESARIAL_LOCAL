from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from enterprise_deliverable_registry import (
    DeliverableRegistryError,
    GovernedDeliverableRegistry,
)

ENTERPRISE_QA_VERSION = "r10.19a"


def _norm(value: Any) -> str:
    text = str(value or "").strip().lower()
    replacements = {
        "á": "a", "é": "e", "í": "i",
        "ó": "o", "ú": "u", "ü": "u", "ñ": "n",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    text = re.sub(r"[^a-z0-9_]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _question_hash(question: str) -> str:
    return hashlib.sha256(
        str(question or "").encode("utf-8")
    ).hexdigest()


def _extract_dashboard_payload(html_path: Path) -> Dict[str, Any]:
    """
    Extrae de forma determin\u00edstica el objeto JSON asignado a DATA
    dentro del dashboard HTML.

    No usa regex para capturar todo el objeto porque despu\u00e9s de DATA
    existe JavaScript adicional dentro del mismo <script>.
    """
    text = html_path.read_text(
        encoding="utf-8",
        errors="strict",
    )

    markers = (
        "const DATA=",
        "const DATA =",
        "window.DATA=",
        "window.DATA =",
    )

    payload_start = None

    for marker in markers:
        pos = text.find(marker)
        if pos >= 0:
            payload_start = pos + len(marker)
            break

    if payload_start is None:
        raise ValueError(
            "DASHBOARD_PAYLOAD_MARKER_NOT_FOUND: "
            "no se encontr\u00f3 la asignaci\u00f3n DATA en el HTML"
        )

    while (
        payload_start < len(text)
        and text[payload_start].isspace()
    ):
        payload_start += 1

    decoder = json.JSONDecoder()

    try:
        obj, consumed = decoder.raw_decode(
            text[payload_start:]
        )
    except json.JSONDecodeError as exc:
        raise ValueError(
            "DASHBOARD_PAYLOAD_INVALID_JSON: "
            f"{exc}"
        ) from exc

    if not isinstance(obj, dict):
        raise ValueError(
            "DASHBOARD_PAYLOAD_INVALID_TYPE: "
            "DATA no contiene un objeto JSON"
        )

    return obj


def _dashboard_spec(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Resuelve la especificaci\u00f3n gobernada del dashboard desde el
    payload persistido en el HTML.

    Autoridad can\u00f3nica R10.18+:
        payload.plan.execution_plan.dashboard_spec
    """
    plan = payload.get("plan")

    if not isinstance(plan, dict):
        raise ValueError(
            "DASHBOARD_PLAN_NOT_FOUND"
        )

    execution_plan = plan.get("execution_plan")

    if isinstance(execution_plan, dict):
        spec = execution_plan.get("dashboard_spec")
        if isinstance(spec, dict):
            return spec

    # Fallbacks de compatibilidad, sin inventar estructura.
    spec = plan.get("dashboard_spec")
    if isinstance(spec, dict):
        return spec

    spec = payload.get("dashboard_spec")
    if isinstance(spec, dict):
        return spec

    raise ValueError(
        "DASHBOARD_SPEC_NOT_FOUND"
    )


def _components(spec: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [
        item
        for item in list(spec.get("components") or [])
        if isinstance(item, dict)
    ]


def _find_component(
    spec: Dict[str, Any],
    component_id: str,
) -> Optional[Dict[str, Any]]:
    for item in _components(spec):
        if str(item.get("id") or "") == component_id:
            return item
    return None


def _metric_alias(question: str) -> Optional[str]:
    q = _norm(question)

    aliases = [
        (
            "kpi:freight",
            (
                "flete total",
                "costo de flete",
                "costo flete",
                "freight",
                "fletes",
            ),
        ),
        (
            "kpi:revenue",
            (
                "venta total",
                "ventas totales",
                "cuanto vendimos",
                "ventas",
                "revenue",
            ),
        ),
        (
            "kpi:profit",
            (
                "utilidad total",
                "utilidad",
                "ganancia",
                "profit",
            ),
        ),
        (
            "kpi:margin",
            (
                "margen",
                "margen porcentual",
                "margin",
            ),
        ),
        (
            "kpi:operations",
            (
                "operaciones",
                "numero de operaciones",
                "cuantas operaciones",
            ),
        ),
        (
            "kpi:active_customers",
            (
                "clientes activos",
                "cuantos clientes",
                "clientes unicos",
            ),
        ),
        (
            "kpi:active_products",
            (
                "productos activos",
                "cuantos productos",
            ),
        ),
        (
            "kpi:active_sellers",
            (
                "vendedores activos",
                "cuantos vendedores",
            ),
        ),
    ]

    for component_id, patterns in aliases:
        if any(_norm(p) in q for p in patterns):
            return component_id

    return None


def _component_value(
    component: Dict[str, Any],
    payload: Dict[str, Any],
) -> Any:
    for key in (
        "value",
        "result",
        "computed_value",
        "display_value",
    ):
        if key in component and component.get(key) is not None:
            return component.get(key)

    analytical_results = payload.get("analytical_results")
    if isinstance(analytical_results, dict):
        cid = str(component.get("id") or "")
        item = analytical_results.get(cid)

        if isinstance(item, dict):
            for key in (
                "value",
                "result",
                "computed_value",
            ):
                if item.get(key) is not None:
                    return item.get(key)

        if item is not None and not isinstance(item, dict):
            return item

    return None


def _blocked_answer(
    *,
    question: str,
    component: Dict[str, Any],
    run: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "schema_version": ENTERPRISE_QA_VERSION,
        "status": "BLOCKED",
        "question": question,
        "question_hash_sha256": _question_hash(question),
        "intent": {
            "type": "metric_query",
            "component_id": component.get("id"),
        },
        "answer": None,
        "reason": (
            component.get("reason")
            or component.get("blocked_reason")
            or "capability_blocked"
        ),
        "evidence": [
            {
                "component_id": component.get("id"),
                "status": component.get("status"),
                "semantic_role": component.get("semantic_role"),
                "columns": component.get("columns"),
                "formula": component.get("formula"),
                "dependencies": component.get("dependencies"),
            }
        ],
        "provenance": {
            "run_id": run.get("run_id"),
            "source_fingerprint_sha256":
                run.get("source_fingerprint_sha256"),
            "manifest_fingerprint_sha256":
                run.get("manifest_fingerprint_sha256"),
            "record_fingerprint_sha256":
                run.get("record_fingerprint_sha256"),
        },
        "governance": {
            "fail_closed": True,
            "llm_computational_authority": False,
            "llm_formula_authority": False,
            "source_data_precedence": True,
            "blocked_values_not_inferred": True,
        },
    }


def answer_enterprise_question(
    *,
    registry: GovernedDeliverableRegistry,
    scope: Dict[str, Any],
    run_id: str,
    question: str,
) -> Dict[str, Any]:
    question = str(question or "").strip()

    if not question:
        raise ValueError("QUESTION_REQUIRED")

    run = registry.get(
        scope,
        run_id,
        verify_artifacts=True,
    )

    html_item = None

    for item in list(run.get("deliverables") or []):
        if item.get("format") == "html":
            html_item = item
            break

    if not html_item:
        raise ValueError(
            "HTML_DELIVERABLE_REQUIRED"
        )

    html_path = registry.artifact_path(
        scope,
        run_id,
        "html",
    )

    payload = _extract_dashboard_payload(html_path)
    spec = _dashboard_spec(payload)

    qnorm = _norm(question)

    if (
        "cobertura" in qnorm
        or "coverage" in qnorm
    ):
        coverage = spec.get("coverage")
        coverage = (
            coverage
            if isinstance(coverage, dict)
            else {}
        )

        return {
            "schema_version": ENTERPRISE_QA_VERSION,
            "status": "ANSWERED",
            "question": question,
            "question_hash_sha256":
                _question_hash(question),
            "intent": {
                "type": "coverage_query",
            },
            "answer": {
                "requested":
                    coverage.get("requested"),
                "supported":
                    coverage.get("supported"),
                "derivable":
                    coverage.get("derivable"),
                "blocked":
                    coverage.get("blocked"),
                "fulfilled":
                    coverage.get("fulfilled"),
                "percent":
                    coverage.get("percent"),
            },
            "evidence": [
                {
                    "source": "dashboard_spec.coverage",
                }
            ],
            "provenance": {
                "run_id": run.get("run_id"),
                "source_fingerprint_sha256":
                    run.get(
                        "source_fingerprint_sha256"
                    ),
                "manifest_fingerprint_sha256":
                    run.get(
                        "manifest_fingerprint_sha256"
                    ),
                "record_fingerprint_sha256":
                    run.get(
                        "record_fingerprint_sha256"
                    ),
            },
            "governance": {
                "fail_closed": True,
                "llm_computational_authority": False,
                "llm_formula_authority": False,
                "source_data_precedence": True,
            },
        }

    if (
        "bloquead" in qnorm
        or "blocked" in qnorm
    ):
        blocked = [
            {
                "id": item.get("id"),
                "type": item.get("type"),
                "reason":
                    item.get("reason")
                    or item.get("blocked_reason"),
            }
            for item in _components(spec)
            if str(
                item.get("status") or ""
            ).upper() == "BLOCKED"
        ]

        return {
            "schema_version": ENTERPRISE_QA_VERSION,
            "status": "ANSWERED",
            "question": question,
            "question_hash_sha256":
                _question_hash(question),
            "intent": {
                "type": "blocked_capabilities_query",
            },
            "answer": blocked,
            "evidence": [
                {
                    "source":
                        "dashboard_spec.components",
                    "blocked_count": len(blocked),
                }
            ],
            "provenance": {
                "run_id": run.get("run_id"),
                "source_fingerprint_sha256":
                    run.get(
                        "source_fingerprint_sha256"
                    ),
                "manifest_fingerprint_sha256":
                    run.get(
                        "manifest_fingerprint_sha256"
                    ),
                "record_fingerprint_sha256":
                    run.get(
                        "record_fingerprint_sha256"
                    ),
            },
            "governance": {
                "fail_closed": True,
                "llm_computational_authority": False,
                "llm_formula_authority": False,
                "source_data_precedence": True,
            },
        }

    if (
        "archivo fuente" in qnorm
        or "fuente" == qnorm
        or "archivo origen" in qnorm
    ):
        return {
            "schema_version": ENTERPRISE_QA_VERSION,
            "status": "ANSWERED",
            "question": question,
            "question_hash_sha256":
                _question_hash(question),
            "intent": {
                "type": "source_query",
            },
            "answer": {
                "source_fingerprint_sha256":
                    run.get(
                        "source_fingerprint_sha256"
                    ),
            },
            "evidence": [
                {
                    "source":
                        "deliverable_registry",
                }
            ],
            "provenance": {
                "run_id": run.get("run_id"),
                "manifest_fingerprint_sha256":
                    run.get(
                        "manifest_fingerprint_sha256"
                    ),
                "record_fingerprint_sha256":
                    run.get(
                        "record_fingerprint_sha256"
                    ),
            },
            "governance": {
                "fail_closed": True,
                "llm_computational_authority": False,
                "llm_formula_authority": False,
            },
        }

    if (
        "formatos" in qnorm
        or "entregables" in qnorm
    ):
        formats = [
            item.get("format")
            for item in list(
                run.get("deliverables") or []
            )
            if item.get("format")
        ]

        return {
            "schema_version": ENTERPRISE_QA_VERSION,
            "status": "ANSWERED",
            "question": question,
            "question_hash_sha256":
                _question_hash(question),
            "intent": {
                "type": "deliverables_query",
            },
            "answer": {
                "formats": formats,
            },
            "evidence": [
                {
                    "source":
                        "deliverable_registry",
                }
            ],
            "provenance": {
                "run_id": run.get("run_id"),
                "manifest_fingerprint_sha256":
                    run.get(
                        "manifest_fingerprint_sha256"
                    ),
                "record_fingerprint_sha256":
                    run.get(
                        "record_fingerprint_sha256"
                    ),
            },
            "governance": {
                "fail_closed": True,
                "llm_computational_authority": False,
                "llm_formula_authority": False,
            },
        }

    component_id = _metric_alias(question)

    if not component_id:
        return {
            "schema_version": ENTERPRISE_QA_VERSION,
            "status": "UNRESOLVED",
            "question": question,
            "question_hash_sha256":
                _question_hash(question),
            "intent": {
                "type": "unknown",
            },
            "answer": None,
            "reason":
                "question_not_supported_by_r10_19a",
            "provenance": {
                "run_id": run.get("run_id"),
            },
            "governance": {
                "fail_closed": True,
                "llm_computational_authority": False,
                "llm_formula_authority": False,
                "unsupported_questions_not_guessed":
                    True,
            },
        }

    component = _find_component(
        spec,
        component_id,
    )

    if not component:
        return {
            "schema_version": ENTERPRISE_QA_VERSION,
            "status": "UNRESOLVED",
            "question": question,
            "question_hash_sha256":
                _question_hash(question),
            "intent": {
                "type": "metric_query",
                "component_id": component_id,
            },
            "answer": None,
            "reason":
                "component_not_present_in_governed_spec",
            "provenance": {
                "run_id": run.get("run_id"),
            },
            "governance": {
                "fail_closed": True,
                "llm_computational_authority": False,
                "llm_formula_authority": False,
            },
        }

    status = str(
        component.get("status") or ""
    ).upper()

    if status == "BLOCKED":
        return _blocked_answer(
            question=question,
            component=component,
            run=run,
        )

    if status not in {
        "SUPPORTED",
        "DERIVABLE",
    }:
        return {
            "schema_version": ENTERPRISE_QA_VERSION,
            "status": "UNRESOLVED",
            "question": question,
            "question_hash_sha256":
                _question_hash(question),
            "answer": None,
            "reason":
                "component_has_invalid_status",
            "governance": {
                "fail_closed": True,
                "llm_computational_authority": False,
                "llm_formula_authority": False,
            },
        }

    value = _component_value(
        component,
        payload,
    )

    if value is None:
        return {
            "schema_version": ENTERPRISE_QA_VERSION,
            "status": "UNRESOLVED",
            "question": question,
            "question_hash_sha256":
                _question_hash(question),
            "intent": {
                "type": "metric_query",
                "component_id": component_id,
            },
            "answer": None,
            "reason":
                "governed_component_has_no_persisted_value",
            "evidence": [
                {
                    "component_id":
                        component.get("id"),
                    "status":
                        component.get("status"),
                    "formula":
                        component.get("formula"),
                    "columns":
                        component.get("columns"),
                }
            ],
            "provenance": {
                "run_id": run.get("run_id"),
                "source_fingerprint_sha256":
                    run.get(
                        "source_fingerprint_sha256"
                    ),
                "manifest_fingerprint_sha256":
                    run.get(
                        "manifest_fingerprint_sha256"
                    ),
            },
            "governance": {
                "fail_closed": True,
                "llm_computational_authority": False,
                "llm_formula_authority": False,
                "missing_values_not_recomputed":
                    True,
            },
        }

    return {
        "schema_version": ENTERPRISE_QA_VERSION,
        "status": "ANSWERED",
        "question": question,
        "question_hash_sha256":
            _question_hash(question),
        "intent": {
            "type": "metric_query",
            "component_id": component_id,
        },
        "answer": {
            "value": value,
            "component_status": status,
        },
        "evidence": [
            {
                "component_id":
                    component.get("id"),
                "status":
                    component.get("status"),
                "semantic_role":
                    component.get("semantic_role"),
                "columns":
                    component.get("columns"),
                "formula":
                    component.get("formula"),
                "dependencies":
                    component.get("dependencies"),
            }
        ],
        "provenance": {
            "run_id": run.get("run_id"),
            "source_fingerprint_sha256":
                run.get(
                    "source_fingerprint_sha256"
                ),
            "manifest_fingerprint_sha256":
                run.get(
                    "manifest_fingerprint_sha256"
                ),
            "record_fingerprint_sha256":
                run.get(
                    "record_fingerprint_sha256"
                ),
        },
        "governance": {
            "fail_closed": True,
            "llm_computational_authority": False,
            "llm_formula_authority": False,
            "source_data_precedence": True,
        },
    }

