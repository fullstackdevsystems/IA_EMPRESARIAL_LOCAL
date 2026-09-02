from pathlib import Path
import sys
def check(name,cond):
    if not cond: print("FAIL",name); raise AssertionError(name)
    print("PASS",name)
if len(sys.argv)<2: raise SystemExit("Uso: python test_r10_16e_e2e_governed_knowledge_approval.py <dashboard.html>")
p=Path(sys.argv[1]); t=p.read_text(encoding="utf-8",errors="replace")
print("\n=== R10.16E E2E GOVERNED KNOWLEDGE APPROVAL ===")
print("Archivo:",p)
check("r10_16c_preserved",'"schema_version":"r10.16c"' in t)
check("r10_16b_preserved",'"schema_version":"r10.16b"' in t)
check("r10_16a_preserved",'"schema_version":"r10.16a"' in t)
check("r10_15f_preserved",'"schema_version":"r10.15f"' in t)
check("formula_authority_false",'"formula_authority":false' in t)
check("source_data_precedence",'"source_data_precedence":true' in t)
check("freight_still_blocked",'"id":"kpi:freight"' in t and '"status":"BLOCKED"' in t)
check("coverage_still_93_94",'"percent":93.94' in t or '"coverage_pct":93.94' in t)
print("\nPASS R10.16E E2E GOVERNED KNOWLEDGE APPROVAL")
