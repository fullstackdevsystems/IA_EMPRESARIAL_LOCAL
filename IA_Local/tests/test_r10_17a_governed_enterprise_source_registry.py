from pathlib import Path
import json
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
S = ROOT / "scripts"
if str(S) not in sys.path:
    sys.path.insert(0, str(S))

from enterprise_source_registry import ENTERPRISE_SOURCE_REGISTRY_VERSION, load_governed_enterprise_source_registry, resolve_governed_enterprise_sources

def check(name, cond):
    if not cond:
        print("FAIL", name)
        raise AssertionError(name)
    print("PASS", name)

print("\n=== R10.17A GOVERNED ENTERPRISE SOURCE REGISTRY ===")
with tempfile.TemporaryDirectory() as td:
    p = Path(td) / "sources.json"
    p.write_text(json.dumps({
        "schema_version":"r10.17a","registry_id":"demo","sources_version":"1",
        "sources":[
            {"source_id":"demo.sales.xlsx","kind":"excel","status":"ENABLED","name":"Ventas Excel","scope":{"company_id":"DEMO"},"locator":{"relative_path":"workspace/Entrada/ventas.xlsx"},"access":{"mode":"read_only"}},
            {"source_id":"demo.erp.sql","kind":"sql_server","status":"ENABLED","name":"ERP SQL","scope":{"company_id":"DEMO"},"locator":{"server":"SQL01","database":"ERP"},"credential_ref":"env:IA_SQL_ERP","access":{"mode":"read_only"}},
            {"source_id":"demo.disabled.csv","kind":"csv","status":"DISABLED","name":"CSV viejo","scope":{"company_id":"DEMO"},"locator":{"relative_path":"workspace/Entrada/viejo.csv"},"access":{"mode":"read_only"}}
        ]
    }), encoding="utf-8")
    registry = load_governed_enterprise_source_registry(str(p))
    check("version", ENTERPRISE_SOURCE_REGISTRY_VERSION=="r10.17a")
    check("loaded", registry["status"]=="LOADED")
    check("source_count", registry["source_count"]==3)
    check("enabled_count", registry["enabled_source_count"]==2)
    resolved = resolve_governed_enterprise_sources(registry=registry, context={"company_id":"DEMO"})
    check("resolved", resolved["status"]=="RESOLVED")
    check("enabled_only", resolved["source_count"]==2)
    check("credential_value_not_exposed", all("credential_ref" not in x for x in resolved["sources"]))
    check("credential_presence_only", any(x["credential_ref_present"] for x in resolved["sources"]))
    check("read_only", resolved["governance"]["read_only"] is True)
    wrong_scope = resolve_governed_enterprise_sources(registry=registry, context={"company_id":"OTHER"})
    check("cross_company_empty", wrong_scope["source_count"]==0)

    def write_bad(name, source):
        q = Path(td) / name
        q.write_text(json.dumps({"schema_version":"r10.17a","registry_id":"bad","sources_version":"1","sources":[source]}), encoding="utf-8")
        return q

    bad_secret = write_bad("bad_secret.json", {"source_id":"bad.sql","kind":"sql_server","status":"ENABLED","name":"Bad SQL","scope":{},"locator":{"server":"SQL01","database":"ERP","password":"SECRET"},"access":{"mode":"read_only"}})
    check("inline_secret_rejected", load_governed_enterprise_source_registry(str(bad_secret))["status"]=="INVALID")

    bad_write = write_bad("bad_write.json", {"source_id":"bad.write","kind":"csv","status":"ENABLED","name":"Bad Write","scope":{},"locator":{"relative_path":"workspace/Entrada/x.csv"},"access":{"mode":"read_write"}})
    check("write_access_rejected", load_governed_enterprise_source_registry(str(bad_write))["status"]=="INVALID")

    traversal = write_bad("traversal.json", {"source_id":"bad.path","kind":"excel","status":"ENABLED","name":"Bad Path","scope":{},"locator":{"relative_path":"../secret.xlsx"},"access":{"mode":"read_only"}})
    check("path_traversal_rejected", load_governed_enterprise_source_registry(str(traversal))["status"]=="INVALID")

    inline_sql = write_bad("inline_sql.json", {"source_id":"bad.query","kind":"sql_server","status":"ENABLED","name":"Bad SQL Query","scope":{},"locator":{"server":"SQL01","database":"ERP","query":"DELETE FROM X"},"credential_ref":"env:IA_SQL_ERP","access":{"mode":"read_only"}})
    check("inline_sql_rejected", load_governed_enterprise_source_registry(str(inline_sql))["status"]=="INVALID")

default = load_governed_enterprise_source_registry(str(ROOT/"config"/"enterprise_sources.json"))
check("default_empty", default["status"]=="EMPTY" and default["source_count"]==0)
check("credentials_external", default["governance"]["credentials_must_use_external_reference"] is True)
check("registry_no_connection", default["governance"]["registry_does_not_open_connections"] is True)
check("registry_no_query", default["governance"]["registry_does_not_execute_queries"] is True)
builder=(S/"dashboard_spec_builder.py").read_text(encoding="utf-8",errors="replace")
check("builder_import","load_governed_enterprise_source_registry" in builder)
check("builder_registry_audit",'"enterprise_source_registry"' in builder)
print("\nPASS R10.17A GOVERNED ENTERPRISE SOURCE REGISTRY")
