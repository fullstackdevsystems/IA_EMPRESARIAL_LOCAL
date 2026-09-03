from pathlib import Path
import hashlib
import json
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
S = ROOT / "scripts"
if str(S) not in sys.path:
    sys.path.insert(0, str(S))

from enterprise_deliverable_manifest import (
    build_governed_deliverable_manifest,
    deliverable_manifest_summary_rows,
)
from enterprise_deliverable_registry import (
    DeliverableRegistryError,
    GovernedDeliverableRegistry,
)


def check(name, cond):
    if not cond:
        print("FAIL", name)
        raise AssertionError(name)
    print("PASS", name)


def resign(manifest):
    unsigned = dict(manifest)
    unsigned.pop("manifest_fingerprint_sha256", None)
    canonical = json.dumps(
        unsigned,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    manifest["manifest_fingerprint_sha256"] = hashlib.sha256(
        canonical.encode("utf-8")
    ).hexdigest()
    return manifest


def expect_code(name, code, fn):
    try:
        fn()
    except DeliverableRegistryError as exc:
        check(name, exc.code == code)
        return
    raise AssertionError(f"{name}: no exception")


print()
print("=== R10.18D DELIVERABLE INTEGRITY CLOSURE ===")

fp = hashlib.sha256(b"source-r10.18d").hexdigest()
prompt_fp = hashlib.sha256(b"prompt-r10.18d").hexdigest()

plan = {
    "request_prompt_sha256": prompt_fp,
    "prompt_integrity": "r10.18a-cross-format-authority",
    "execution_plan": {
        "version": "test-r10.18d",
        "source_of_truth": "governed-source",
        "coverage_pct": 100.0,
        "dashboard_spec": {
            "schema_version": "test-r10.18d",
            "components": [],
            "coverage": {
                "requested": 34,
                "supported": 23,
                "derivable": 9,
                "blocked": 2,
                "fulfilled": 32,
                "percent": 94.12,
            },
            "source": {},
            "provenance": {"ruleset_version": "test"},
        },
    },
}

intent = {
    "schema_version": "r10.18c",
    "outputs": {"html": True, "pdf": True, "excel": True},
    "requested": ["html", "excel", "pdf"],
    "explicit": True,
    "reason": "resolved_from_prompt",
}

manifest = build_governed_deliverable_manifest(
    dashboard_plan=plan,
    filename="ventas.csv",
    sheet="CSV",
    row_count=2,
    prompt_sha256=prompt_fp,
    source_fingerprint_sha256=fp,
    output_intent=intent,
    source_fingerprint_required=True,
)

check("manifest_ready", manifest.get("status") == "READY")
check(
    "intent_persisted",
    set((manifest.get("request") or {}).get("requested_formats") or [])
    == {"html", "excel", "pdf"},
)
check(
    "fingerprint_persisted",
    (manifest.get("source") or {}).get("source_fingerprint_sha256") == fp,
)
check(
    "closure_version",
    (manifest.get("governance") or {}).get("integrity_closure_version")
    == "r10.18d",
)
summary = manifest.get("summary") or {}
check("manifest_requested_count", summary.get("requested_count") == 34)
check("manifest_fulfilled_count", summary.get("fulfilled_count") == 32)
check("manifest_blocked_count", summary.get("blocked_count") == 2)
check("manifest_canonical_coverage", summary.get("coverage_pct") == 94.12)

rows = {
    row["Campo"]: row["Valor"]
    for row in deliverable_manifest_summary_rows(manifest)
}
check("fingerprint_visible", rows.get("Fingerprint de fuente") == fp)
check(
    "formats_visible",
    set(str(rows.get("Formatos solicitados") or "").split(", "))
    == {"html", "excel", "pdf"},
)

scope = {
    "company_id": "empresa-local",
    "user_id": "admin-local",
    "business_unit": None,
    "branch": None,
}

with tempfile.TemporaryDirectory() as td:
    reports = Path(td)
    (reports / "demo.html").write_text("<html>ok</html>", encoding="utf-8")
    (reports / "demo.xlsx").write_bytes(b"xlsx-test")
    (reports / "demo.pdf").write_bytes(b"%PDF-test")

    registry = GovernedDeliverableRegistry(reports)

    outputs = {
        "html": "demo.html",
        "excel": "demo.xlsx",
        "pdf": "demo.pdf",
    }

    run = registry.register(
        scope=scope,
        run_id="run-r1018d-valid",
        manifest=manifest,
        outputs=outputs,
        domain="test",
    )

    check("registered_ready", run.get("status") == "READY")
    check(
        "record_source_fingerprint",
        run.get("source_fingerprint_sha256") == fp,
    )
    check(
        "record_intent_verified",
        (run.get("governance") or {}).get("output_intent_verified") is True,
    )
    check(
        "record_source_verified",
        (run.get("governance") or {}).get("source_fingerprint_verified") is True,
    )

    blocked_manifest = json.loads(json.dumps(manifest))
    blocked_manifest["status"] = "BLOCKED"
    blocked_manifest["reason"] = "test_blocked"
    resign(blocked_manifest)
    expect_code(
        "blocked_manifest_rejected",
        "MANIFEST_NOT_READY",
        lambda: registry.register(
            scope=scope,
            run_id="run-r1018d-blocked",
            manifest=blocked_manifest,
            outputs=outputs,
            domain="test",
        ),
    )

    missing_fp = json.loads(json.dumps(manifest))
    missing_fp["source"]["source_fingerprint_sha256"] = None
    resign(missing_fp)
    expect_code(
        "missing_source_fingerprint_rejected",
        "SOURCE_FINGERPRINT_REQUIRED",
        lambda: registry.register(
            scope=scope,
            run_id="run-r1018d-no-fp",
            manifest=missing_fp,
            outputs=outputs,
            domain="test",
        ),
    )

    expect_code(
        "output_intent_mismatch_rejected",
        "OUTPUT_INTENT_MISMATCH",
        lambda: registry.register(
            scope=scope,
            run_id="run-r1018d-mismatch",
            manifest=manifest,
            outputs={"html": "demo.html", "pdf": "demo.pdf", "excel": None},
            domain="test",
        ),
    )

print()
print("PASS R10.18D DELIVERABLE INTEGRITY CLOSURE")
