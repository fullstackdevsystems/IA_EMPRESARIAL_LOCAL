from pathlib import Path
import sys
import tempfile
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]; SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path: sys.path.insert(0, str(SCRIPTS))
import analizador_universal as analyzer
from enterprise_sql_gateway import EnterpriseSqlConnectionStore, EnterpriseSqlError, EnterpriseSqlExecutor, SqlServerPyodbcProvider, validate_query_plan

SCOPE = {"company_id":"empresa-a","user_id":"ana","business_unit":None,"branch":None}
OTHER = {"company_id":"empresa-b","user_id":"ana","business_unit":None,"branch":None}
def check(n, ok):
    if not ok: raise AssertionError(n)
    print("PASS", n)
def denied(n, code, fn):
    try: fn()
    except EnterpriseSqlError as exc: check(n, exc.code == code); return
    raise AssertionError(n)
class FakeProvider:
    def __init__(self): self.closed = True
    def discover(self, profile): return [{"schema":"dbo","name":"Orders","type":"TABLE","columns":[{"name":"Código","type":"nvarchar","nullable":False}]},{"schema":"ops","name":"WorkOrders","type":"TABLE","columns":[]}]
    def execute(self, profile, sql, parameters, timeout_seconds): return {"columns":["Código","Descripción"],"rows":[[i, "área"] for i in range(600)]}

print("\n=== R10.19C GOVERNED SQL SERVER INTELLIGENCE ===")
gateway_source = (SCRIPTS / "enterprise_sql_gateway.py").read_text(encoding="utf-8")
check("pyodbc_cursor_timeout_compatible", "cur.timeout" not in gateway_source)
with tempfile.TemporaryDirectory() as td:
    store=EnterpriseSqlConnectionStore(Path(td)/"sql")
    p=store.register(scope=SCOPE,connection_id="conn-a",server="sql01",database="ERP",auth_mode="integrated",credential_ref="env:ERP_SQL_CONN",allowed_schemas=["dbo"],allowed_tables=["dbo.Orders"])
    check("profile_registered_no_secret", p["read_only"] and "password" not in str(p).lower() and "ERP_SQL_CONN" in p["credential_ref"])
    check("same_scope_get", store.get(SCOPE,"conn-a")["database"]=="ERP")
    denied("wrong_scope_blocked","SQL_CONNECTION_NOT_FOUND",lambda:store.get(OTHER,"conn-a"))
    fake=FakeProvider(); ex=EnterpriseSqlExecutor(store,fake)
    try:
        SqlServerPyodbcProvider().discover(p)
    except EnterpriseSqlError as exc:
        check("real_provider_import_safe", exc.code in {"SQL_DRIVER_NOT_AVAILABLE", "SQL_CREDENTIAL_UNAVAILABLE"})
    else:
        raise AssertionError("real_provider_import_safe")
    schema=ex.discover(SCOPE,"conn-a"); check("discovery_allowlist",len(schema["objects"])==1 and schema["objects"][0]["name"]=="Orders")
    plan={"operation":"SELECT","sql":"SELECT Código FROM dbo.Orders WHERE Código = ?","parameters":["á"],"limit":6000,"timeout_seconds":10}
    valid=validate_query_plan(p,plan); check("select_limit_fingerprint",valid["limit"]==5000 and len(valid["query_fingerprint_sha256"])==64)
    result=ex.execute(SCOPE,"conn-a",plan); check("deterministic_rows_truncated",result["row_count"]==600 and result["truncated"] is False and result["columns"]==["Código","Descripción"])
    check("provenance_safe",result["provenance"]["provider"]=="sqlserver" and "password" not in str(result["provenance"]).lower())
    for label,sql,code in [("insert","INSERT INTO dbo.Orders VALUES(1)","SQL_QUERY_NOT_READ_ONLY"),("update","UPDATE dbo.Orders SET x=1","SQL_QUERY_NOT_READ_ONLY"),("delete","DELETE FROM dbo.Orders","SQL_QUERY_NOT_READ_ONLY"),("drop","DROP TABLE dbo.Orders","SQL_QUERY_NOT_READ_ONLY"),("exec","EXEC x","SQL_QUERY_NOT_READ_ONLY"),("multiple","SELECT * FROM dbo.Orders; DELETE FROM dbo.Orders","SQL_MULTIPLE_STATEMENTS_BLOCKED"),("comment","SELECT * FROM dbo.Orders -- x","SQL_POLICY_VIOLATION"),("external","SELECT * FROM OtherDb.dbo.Orders","SQL_DATABASE_NOT_ALLOWED"),("table","SELECT * FROM ops.WorkOrders","SQL_OBJECT_NOT_ALLOWED")]:
        denied(label,code,lambda sql=sql:validate_query_plan(p,{"operation":"SELECT","sql":sql}))
    denied("timeout", "SQL_TIMEOUT", lambda: validate_query_plan(p,{"sql":"SELECT * FROM dbo.Orders","timeout_seconds":0}))
    denied("ambiguous", "SQL_QUERY_NOT_READ_ONLY", lambda: validate_query_plan(p,{"sql":"WITH x AS (SELECT 1) SELECT * FROM dbo.Orders"}))
    tamper=store._path(SCOPE,"conn-a"); tamper.write_text(tamper.read_text(encoding="utf-8").replace("sql01","changed"),encoding="utf-8")
    denied("tamper_fail_closed","SQL_CONNECTION_INTEGRITY_MISMATCH",lambda:store.get(SCOPE,"conn-a"))
    old_reports=analyzer.base.REPORTES; analyzer.base.REPORTES=Path(td)/"api-reports"; analyzer.base.REPORTES.mkdir()
    try:
        with TestClient(analyzer.app) as client:
            api=client.get("/api/sql/connections"); check("api_connections",api.status_code==200 and api.json()["items"]==[])
            blocked_api=client.post("/api/sql/query",json={"connection_id":"missing","query_plan":{"sql":"UPDATE dbo.Orders SET x=1"}})
            check("api_error_contract",blocked_api.status_code==404 and blocked_api.json()["detail"]["code"]=="SQL_CONNECTION_NOT_FOUND")
    finally: analyzer.base.REPORTES=old_reports
print("PASS R10.19C GOVERNED SQL SERVER INTELLIGENCE")
