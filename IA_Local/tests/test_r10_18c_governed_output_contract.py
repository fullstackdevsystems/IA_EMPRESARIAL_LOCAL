from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from enterprise_output_contract import (
    ENTERPRISE_OUTPUT_CONTRACT_VERSION,
    OutputContractError,
    compile_output_contract,
    finalize_output_contract,
    verify_output_contract_fingerprint,
)


def check(name, condition):
    if not condition:
        print("FAIL", name)
        raise AssertionError(name)
    print("PASS", name)


def blocked(name, code, action):
    try:
        action()
    except OutputContractError as exc:
        check(name, exc.code == code)
        return
    raise AssertionError(name)


print("\n=== R10.18C GOVERNED OUTPUT CONTRACT ===")
ambiguous = compile_output_contract("Genera dashboard HTML, PDF y Excel con ventas. No calcules flete sin una regla aprobada.")
check("version", ENTERPRISE_OUTPUT_CONTRACT_VERSION == "r10.18c")
check("all_explicit_formats", all(item["requested"] for item in ambiguous["formats"].values()))
check("unrelated_negation_scoped", ambiguous["formats"]["excel"]["reason"] == "explicit_request")
pdf_only = compile_output_contract("Genera solo PDF ejecutivo con riesgos")
check("pdf_only", pdf_only["formats"]["pdf"]["requested"] and not pdf_only["formats"]["html"]["requested"] and not pdf_only["formats"]["excel"]["requested"])
without_excel = compile_output_contract("Analiza completamente, sin Excel")
check("explicit_excel_exclusion", not without_excel["formats"]["excel"]["requested"] and without_excel["formats"]["html"]["requested"] and without_excel["formats"]["pdf"]["requested"])
without_pdf = compile_output_contract("Genera HTML y Excel; no generar PDF")
check("explicit_pdf_exclusion", without_pdf["formats"]["html"]["requested"] and without_pdf["formats"]["excel"]["requested"] and not without_pdf["formats"]["pdf"]["requested"])
defaulted = compile_output_contract("Analiza tendencias y riesgos")
check("default_three_formats", all(item["requested"] for item in defaulted["formats"].values()))
blocked("all_formats_excluded", "NO_OUTPUT_REQUESTED", lambda: compile_output_contract("Sin HTML, sin PDF y sin Excel"))
tampered = dict(ambiguous)
tampered["status"] = "BLOCKED"
blocked("contract_tamper_blocked", "OUTPUT_CONTRACT_INTEGRITY_MISMATCH", lambda: verify_output_contract_fingerprint(tampered))

with tempfile.TemporaryDirectory() as td:
    reports = Path(td)
    (reports / "a.html").write_text("html", encoding="utf-8")
    (reports / "a.pdf").write_bytes(b"pdf")
    (reports / "a.xlsx").write_bytes(b"xlsx")
    completed = finalize_output_contract(ambiguous, {"html":"a.html", "pdf":"a.pdf", "excel":"a.xlsx"}, reports)
    check("complete", completed["status"] == "COMPLETE")
    check("all_generated", all(item["status"] == "GENERATED" for item in completed["formats"].values()))
    check("artifact_hashes", all(len(item["sha256"]) == 64 for item in completed["formats"].values()))
    blocked("missing_requested_fails_closed", "REQUESTED_OUTPUT_MISSING", lambda: finalize_output_contract(ambiguous, {"html":"a.html", "pdf":"a.pdf", "excel":None}, reports))
    blocked("unrequested_output_fails_closed", "UNREQUESTED_OUTPUT_GENERATED", lambda: finalize_output_contract(pdf_only, {"html":"a.html", "pdf":"a.pdf", "excel":None}, reports))
    blocked("path_traversal_fails_closed", "INVALID_OUTPUT_ARTIFACT", lambda: finalize_output_contract(pdf_only, {"html":None, "pdf":"../a.pdf", "excel":None}, reports))

print("PASS R10.18C GOVERNED OUTPUT CONTRACT")
