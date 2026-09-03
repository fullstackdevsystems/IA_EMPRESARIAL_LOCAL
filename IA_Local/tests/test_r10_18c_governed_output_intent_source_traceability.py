from pathlib import Path
import hashlib, sys
ROOT = Path(__file__).resolve().parents[1]
S = ROOT / "scripts"
if str(S) not in sys.path: sys.path.insert(0, str(S))
from output_intent_resolver import resolve_output_intent
from bi_productivo import compile_report_spec
from universal_prompt_engine import parse_prompt_intent
from enterprise_deliverable_manifest import build_governed_deliverable_manifest

def check(name, cond):
    if not cond: print("FAIL", name); raise AssertionError(name)
    print("PASS", name)

print("\n=== R10.18C GOVERNED OUTPUT INTENT & SOURCE TRACEABILITY ===")
cases = [
("Genera también un Excel empresarial profesional", {"excel":True}),
("Quiero dashboard, Excel y PDF", {"html":True,"excel":True,"pdf":True}),
("Solo PDF", {"html":False,"excel":False,"pdf":True}),
("Dashboard y PDF, sin Excel", {"html":True,"excel":False,"pdf":True}),
("No generes PDF; quiero Excel", {"html":False,"excel":True,"pdf":False}),
("Genera los tres formatos", {"html":True,"excel":True,"pdf":True}),
]
for i,(prompt,expected) in enumerate(cases,1):
    resolved=resolve_output_intent(prompt)
    spec=compile_report_spec(prompt)
    for key,value in expected.items():
        check(f"resolver_{i}_{key}", resolved["outputs"][key] is value)
        check(f"compile_{i}_{key}", spec["outputs"][key] is value)
check("single_authority_parse_excel", "excel" in parse_prompt_intent("Genera también un Excel empresarial profesional").outputs)
check("single_authority_parse_all", set(parse_prompt_intent("Quiero dashboard, Excel y PDF").outputs)=={"html","excel","pdf"})
fp=hashlib.sha256(b"source-real").hexdigest()
plan={"request_prompt_sha256":hashlib.sha256(b"prompt").hexdigest(),"prompt_integrity":"r10.18c-test","execution_plan":{"version":"test","source_of_truth":"governed-source","dashboard_spec":{"schema_version":"test","components":[],"source":{},"provenance":{}}}}
manifest=build_governed_deliverable_manifest(dashboard_plan=plan,filename="demo.xlsx",sheet="0",row_count=1,prompt_sha256=plan["request_prompt_sha256"],source_fingerprint_sha256=fp)
check("manifest_source_fingerprint", manifest["source"]["source_fingerprint_sha256"]==fp)
check("manifest_fingerprint", len(manifest["manifest_fingerprint_sha256"])==64)
universal=(S/"analizador_universal.py").read_text(encoding="utf-8",errors="replace")
check("universal_propagates_source_fingerprint", "_source_fingerprint_from_meta(meta)" in universal)
print("\nPASS R10.18C GOVERNED OUTPUT INTENT & SOURCE TRACEABILITY")
