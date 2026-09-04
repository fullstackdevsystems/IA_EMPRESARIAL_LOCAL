from __future__ import annotations

import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol

from enterprise_deliverable_registry import normalize_deliverable_scope
from enterprise_tenant_registry import EnterpriseTenantRegistry, assert_tenant_active


ENTERPRISE_SQL_GATEWAY_VERSION = "r10.19c"
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$")
_FORBIDDEN = {"insert", "update", "delete", "merge", "drop", "alter", "create", "truncate", "exec", "execute", "grant", "revoke", "deny", "dbcc", "backup", "restore", "bulk", "openrowset", "opendatasource", "xp_cmdshell", "use"}


class EnterpriseSqlError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code

class EnterpriseSecretStore:
    """Injectable secret boundary; production has no implicit secret fallback."""
    def __init__(self, provider=None): self.provider=provider
    def set(self, reference: str, value: str):
        if not self.provider: raise EnterpriseSqlError("SQL_SECRET_UNAVAILABLE","Secret store no configurado")
        self.provider.set(reference,value)
    def get(self, reference: str):
        if not self.provider: raise EnterpriseSqlError("SQL_SECRET_UNAVAILABLE","Secret store no configurado")
        value=self.provider.get(reference)
        if not value: raise EnterpriseSqlError("SQL_SECRET_UNAVAILABLE","Secret SQL no disponible")
        return value
    def delete(self, reference: str):
        if not self.provider: raise EnterpriseSqlError("SQL_SECRET_UNAVAILABLE","Secret store no configurado")
        self.provider.delete(reference)

def public_sql_profile(record: Dict[str,Any]) -> Dict[str,Any]:
    public = {key:record.get(key) for key in ("connection_id","server","database","auth_mode","driver","timeout_seconds","max_rows","trust_server_certificate","allowed_schemas","allowed_tables","enabled","status","display_name","created_at","updated_at","last_test_at","last_test_status","last_latency_ms","last_error_code","last_discovery_at","last_discovery_status","last_discovery_ms","discovered_object_count","last_query_at","last_query_status","last_query_ms","last_query_row_count")}
    public["secret_configured"] = bool(record.get("secret_reference"))
    return public


class SqlServerProvider(Protocol):
    def discover(self, profile: Dict[str, Any]) -> List[Dict[str, Any]]: ...
    def execute(self, profile: Dict[str, Any], sql: str, parameters: List[Any], timeout_seconds: int) -> Dict[str, Any]: ...


class SqlServerPyodbcProvider:
    """Provider SQL Server opcional; el secret sólo se resuelve en runtime."""
    def __init__(self, secret_store: Optional[EnterpriseSecretStore] = None):
        self.secret_store = secret_store

    @staticmethod
    def _connection_error(exc: Exception) -> EnterpriseSqlError:
        text = str(exc).lower()
        if "login failed" in text or "authentication" in text:
            return EnterpriseSqlError("SQL_AUTH_FAILED", "Autenticación SQL rechazada")
        if "database" in text and ("cannot open" in text or "unavailable" in text):
            return EnterpriseSqlError("SQL_DATABASE_UNAVAILABLE", "Base de datos SQL no disponible")
        return EnterpriseSqlError("SQL_CONNECTION_TEST_FAILED", "No fue posible abrir la conexión SQL")

    def _connect(self, profile: Dict[str, Any], timeout_seconds: int):
        try:
            import pyodbc
        except ImportError as exc:
            raise EnterpriseSqlError("SQL_DRIVER_NOT_AVAILABLE", "Driver SQL Server no disponible") from exc
        import os
        ref = str(profile.get("credential_ref") or "")
        legacy_secret = os.environ.get(ref[4:]) if ref.startswith("env:") else None
        mode = str(profile.get("auth_mode") or "").upper()
        if legacy_secret:
            connection_string = legacy_secret
        elif ref.startswith("env:"):
            raise EnterpriseSqlError("SQL_CREDENTIAL_UNAVAILABLE", "Credencial SQL no disponible")
        elif mode == "WINDOWS_INTEGRATED":
            connection_string = (
                f"DRIVER={{{profile.get('driver') or 'ODBC Driver 18 for SQL Server'}}};"
                f"SERVER={profile.get('server')};DATABASE={profile.get('database')};"
                "Trusted_Connection=yes;"
                f"TrustServerCertificate={'yes' if profile.get('trust_server_certificate') else 'no'};"
            )
        elif mode == "SQL_AUTH":
            reference = str(profile.get("secret_reference") or ref or "")
            if not self.secret_store:
                raise EnterpriseSqlError("SQL_SECRET_UNAVAILABLE", "Secret SQL no disponible")
            password = self.secret_store.get(reference)
            username = str(profile.get("username") or "")
            if not username:
                raise EnterpriseSqlError("SQL_SECRET_UNAVAILABLE", "Usuario SQL no disponible")
            connection_string = (
                f"DRIVER={{{profile.get('driver') or 'ODBC Driver 18 for SQL Server'}}};"
                f"SERVER={profile.get('server')};DATABASE={profile.get('database')};"
                f"UID={username};PWD={password};"
                f"TrustServerCertificate={'yes' if profile.get('trust_server_certificate') else 'no'};"
            )
        else:
            raise EnterpriseSqlError("SQL_CREDENTIAL_UNAVAILABLE", "Credencial SQL no disponible")
        try:
            return pyodbc.connect(connection_string, timeout=timeout_seconds, autocommit=False)
        except Exception as exc:
            raise self._connection_error(exc) from exc

    def test_connection(self, profile: Dict[str, Any], timeout_seconds: int) -> Dict[str, Any]:
        conn = self._connect(profile, timeout_seconds)
        try:
            return {"database": str(profile.get("database") or "")}
        finally:
            try: conn.close()
            except Exception: pass
    def discover(self, profile: Dict[str, Any]) -> List[Dict[str, Any]]:
        conn = self._connect(profile, int(profile.get("timeout_seconds") or 30))
        cur = None
        try:
            cur = conn.cursor()
            cur.execute("SELECT TABLE_SCHEMA, TABLE_NAME, TABLE_TYPE FROM INFORMATION_SCHEMA.TABLES")
            objects = []
            for schema, name, typ in cur.fetchmany(10000):
                cur.execute("SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA=? AND TABLE_NAME=? ORDER BY ORDINAL_POSITION", schema, name)
                columns = [{"name": row[0], "type": row[1], "nullable": row[2] == "YES"} for row in cur.fetchmany(10000)]
                objects.append({"schema": schema, "name": name, "type": typ, "columns": columns})
            return objects
        except EnterpriseSqlError: raise
        except Exception as exc: raise EnterpriseSqlError("SQL_SCHEMA_DISCOVERY_FAILED", "Metadata SQL no disponible") from exc
        finally:
            try:
                if cur: cur.close()
            except Exception: pass
            try: conn.close()
            except Exception: pass
    def execute(self, profile: Dict[str, Any], sql: str, parameters: List[Any], timeout_seconds: int) -> Dict[str, Any]:
        conn = self._connect(profile, timeout_seconds)
        try:
            cur = conn.cursor()
            cur.execute("SET TRANSACTION ISOLATION LEVEL READ COMMITTED")
            cur.execute(sql, parameters)
            columns = [item[0] for item in cur.description] if cur.description else []
            return {"columns": columns, "rows": [list(row) for row in cur.fetchmany(5001)]}
        except EnterpriseSqlError: raise
        except Exception as exc: raise EnterpriseSqlError("SQL_EXECUTION_FAILED", "Ejecución SQL falló") from exc
        finally:
            try: conn.rollback()
            except Exception: pass
            try: conn.close()
            except Exception: pass


def _canonical(value: Dict[str, Any]) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _fingerprint(value: Dict[str, Any]) -> str:
    unsigned = dict(value); unsigned.pop("fingerprint_sha256", None)
    return hashlib.sha256(_canonical(unsigned)).hexdigest()


def _safe(value: Any, code: str) -> str:
    text = str(value or "").strip()
    if not _ID.fullmatch(text) or text in {".", ".."}:
        raise EnterpriseSqlError(code, "Identificador SQL inválido")
    return text


class EnterpriseSqlConnectionStore:
    def __init__(self, root: Path, tenant_registry: Optional[EnterpriseTenantRegistry] = None): self.root = Path(root); self.tenant_registry = tenant_registry
    def _dir(self, scope: Dict[str, Any], create: bool = False) -> Path:
        s = normalize_deliverable_scope(scope); assert_tenant_active(s, self.tenant_registry)
        if create: self.root.mkdir(parents=True, exist_ok=True)
        root = self.root.resolve(); target = root / s["company_id"] / s["user_id"] / (s.get("business_unit") or "_") / (s.get("branch") or "_")
        if create: target.mkdir(parents=True, exist_ok=True)
        try: target.resolve().relative_to(root)
        except ValueError as exc: raise EnterpriseSqlError("SQL_SCOPE_DENIED", "Scope fuera del store SQL") from exc
        return target.resolve()
    def _path(self, scope: Dict[str, Any], connection_id: str, create: bool = False) -> Path:
        return self._dir(scope, create) / f"{_safe(connection_id, 'SQL_CONNECTION_INVALID')}.json"
    def _read(self, path: Path) -> Dict[str, Any]:
        try: record = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc: raise EnterpriseSqlError("SQL_CONNECTION_INVALID", "Profile SQL ilegible") from exc
        if not isinstance(record, dict) or _fingerprint(record) != record.get("fingerprint_sha256"):
            raise EnterpriseSqlError("SQL_CONNECTION_INTEGRITY_MISMATCH", "Profile SQL alterado")
        return record
    def _write(self, scope: Dict[str, Any], connection_id: str, record: Dict[str, Any]) -> None:
        path = self._path(scope, connection_id, True)
        temporary = path.with_suffix(".tmp")
        temporary.write_bytes(_canonical(record))
        temporary.replace(path)
    def register(self, *, scope: Dict[str, Any], connection_id: str, server: str, database: str, auth_mode: str, credential_ref: str = "", allowed_schemas: List[str]=None, allowed_tables: List[str]=None, enabled: bool = True, display_name: str="", driver: str="ODBC Driver 18 for SQL Server", timeout_seconds:int=30, max_rows:int=500, trust_server_certificate:bool=False, secret_reference:str="", username:str="") -> Dict[str, Any]:
        s = normalize_deliverable_scope(scope); path = self._path(s, connection_id, True)
        if path.exists(): raise EnterpriseSqlError("SQL_CONNECTION_ALREADY_EXISTS", "Conexión ya registrada")
        mode=str(auth_mode).upper(); mode="WINDOWS_INTEGRATED" if mode in {"INTEGRATED","WINDOWS"} else mode; allowed_tables=allowed_tables or []; allowed_schemas=allowed_schemas or []
        if mode not in {"WINDOWS_INTEGRATED","SQL_AUTH"}: raise EnterpriseSqlError("SQL_CONNECTION_PROFILE_INVALID","Modo de autenticación inválido")
        if not str(server).strip() or not str(database).strip() or timeout_seconds<1 or timeout_seconds>120 or max_rows<1 or max_rows>5000:
            raise EnterpriseSqlError("SQL_CONNECTION_PROFILE_INVALID", "Profile SQL incompleto o secret ref inválido")
        if mode=="SQL_AUTH" and not str(secret_reference or credential_ref).strip(): raise EnterpriseSqlError("SQL_SECRET_UNAVAILABLE","SQL_AUTH requiere secret_reference")
        tables = [str(x).strip() for x in allowed_tables if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*", str(x).strip())]
        schemas = [str(x).strip() for x in allowed_schemas if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", str(x).strip())]
        if not tables or not schemas or any(item.split(".")[0] not in schemas for item in tables):
            raise EnterpriseSqlError("SQL_ALLOWLIST_REQUIRED", "Allowlist de schemas/tables inválida")
        record = {"schema_version": ENTERPRISE_SQL_GATEWAY_VERSION, "connection_id": _safe(connection_id, "SQL_CONNECTION_INVALID"), "scope": s, "provider": "sqlserver", "server": str(server).strip(), "database": str(database).strip(), "auth_mode":mode, "credential_ref": str(credential_ref).strip(), "secret_reference":str(secret_reference or credential_ref).strip() or None, "username":str(username).strip() or None, "allowed_schemas": schemas, "allowed_tables": tables, "read_only": True, "enabled": bool(enabled), "status":"ACTIVE" if enabled else "DISABLED", "display_name":str(display_name).strip() or None,"driver":driver,"timeout_seconds":timeout_seconds,"max_rows":max_rows,"trust_server_certificate":bool(trust_server_certificate),"created_at": datetime.now(timezone.utc).isoformat(),"updated_at":datetime.now(timezone.utc).isoformat()}
        record["fingerprint_sha256"] = _fingerprint(record); self._write(s, connection_id, record); return dict(record)
    def get(self, scope: Dict[str, Any], connection_id: str) -> Dict[str, Any]:
        path = self._path(scope, connection_id)
        if not path.is_file(): raise EnterpriseSqlError("SQL_CONNECTION_NOT_FOUND", "Conexión SQL no encontrada")
        return self._read(path)
    def list(self, scope: Dict[str, Any]) -> List[Dict[str, Any]]:
        directory = self._dir(scope)
        return [] if not directory.exists() else [self._read(p) for p in sorted(directory.glob("*.json"))]
    def update(self, scope: Dict[str,Any], connection_id: str, **changes) -> Dict[str,Any]:
        record=self.get(scope,connection_id); allowed={"display_name","server","database","driver","timeout_seconds","max_rows","trust_server_certificate","allowed_schemas","allowed_tables","secret_reference","username"}
        if set(changes)-allowed: raise EnterpriseSqlError("SQL_CONNECTION_PROFILE_INVALID","Campo administrativo no permitido")
        if "timeout_seconds" in changes and (isinstance(changes["timeout_seconds"],bool) or not 1<=int(changes["timeout_seconds"])<=120): raise EnterpriseSqlError("SQL_CONNECTION_PROFILE_INVALID","Timeout inválido")
        if "max_rows" in changes and (isinstance(changes["max_rows"],bool) or not 1<=int(changes["max_rows"])<=5000): raise EnterpriseSqlError("SQL_CONNECTION_PROFILE_INVALID","max_rows inválido")
        schemas = changes.get("allowed_schemas", record.get("allowed_schemas") or [])
        tables = changes.get("allowed_tables", record.get("allowed_tables") or [])
        if "allowed_schemas" in changes or "allowed_tables" in changes:
            if not isinstance(schemas, list) or not isinstance(tables, list): raise EnterpriseSqlError("SQL_ALLOWLIST_REQUIRED", "Allowlist de schemas/tables inválida")
            valid_schemas = [str(x).strip() for x in schemas if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", str(x).strip())]
            valid_tables = [str(x).strip() for x in tables if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*", str(x).strip())]
            if len(valid_schemas) != len(schemas) or len(valid_tables) != len(tables) or not valid_schemas or not valid_tables or any(item.split(".")[0] not in valid_schemas for item in valid_tables): raise EnterpriseSqlError("SQL_ALLOWLIST_REQUIRED", "Allowlist de schemas/tables inválida")
            changes["allowed_schemas"], changes["allowed_tables"] = valid_schemas, valid_tables
        for key,value in changes.items(): record[key]=value
        record["updated_at"]=datetime.now(timezone.utc).isoformat(); record["fingerprint_sha256"]=_fingerprint(record); self._write(scope,connection_id,record); return dict(record)
    def disable(self,scope:Dict[str,Any],connection_id:str)->Dict[str,Any]:
        record=self.update(scope,connection_id);record["enabled"]=False;record["status"]="DISABLED";record["updated_at"]=datetime.now(timezone.utc).isoformat();record["fingerprint_sha256"]=_fingerprint(record);self._write(scope,connection_id,record);return record
    def enable(self,scope:Dict[str,Any],connection_id:str)->Dict[str,Any]:
        record=self.update(scope,connection_id);record["enabled"]=True;record["status"]="ACTIVE";record["updated_at"]=datetime.now(timezone.utc).isoformat();record["fingerprint_sha256"]=_fingerprint(record);self._write(scope,connection_id,record);return record
    def record_operation(self, scope: Dict[str, Any], connection_id: str, prefix: str, status: str, latency_ms: float, error_code: Optional[str] = None, discovered_object_count: Optional[int] = None, row_count: Optional[int] = None) -> Dict[str, Any]:
        if prefix not in {"last_test", "last_discovery", "last_query"}:
            raise EnterpriseSqlError("SQL_CONNECTION_PROFILE_INVALID", "Operación SQL inválida")
        record = self.get(scope, connection_id)
        record[f"{prefix}_at"] = datetime.now(timezone.utc).isoformat()
        record[f"{prefix}_status"] = status
        record[f"{prefix}_ms"] = round(float(latency_ms), 3)
        if prefix == "last_test": record["last_latency_ms"] = record[f"{prefix}_ms"]; record["last_error_code"] = error_code
        if discovered_object_count is not None: record["discovered_object_count"] = int(discovered_object_count)
        if row_count is not None: record["last_query_row_count"] = int(row_count)
        record["updated_at"] = datetime.now(timezone.utc).isoformat(); record["fingerprint_sha256"] = _fingerprint(record)
        self._write(scope, connection_id, record)
        return dict(record)

def assert_sql_profile_active(profile:Dict[str,Any])->Dict[str,Any]:
    if not profile.get("enabled",True) or profile.get("status")=="DISABLED": raise EnterpriseSqlError("SQL_CONNECTION_DISABLED","Conexión deshabilitada")
    return profile


_PUBLIC_CONNECTION_ERRORS = {
    "SQL_SECRET_UNAVAILABLE", "SQL_DRIVER_NOT_AVAILABLE", "SQL_AUTH_FAILED",
    "SQL_DATABASE_UNAVAILABLE", "SQL_CONNECTION_TEST_FAILED",
    "SQL_SCHEMA_DISCOVERY_FAILED", "SQL_CONNECTION_DISABLED", "SQL_SCOPE_DENIED",
    "SQL_EXECUTION_FAILED", "SQL_ALLOWLIST_DENIED", "SQL_QUERY_INVALID", "SQL_QUERY_POLICY_BLOCKED",
}
_PUBLIC_CONNECTION_MESSAGES = {
    "SQL_SECRET_UNAVAILABLE": "Secret SQL no disponible",
    "SQL_DRIVER_NOT_AVAILABLE": "Driver SQL Server no disponible",
    "SQL_AUTH_FAILED": "Autenticación SQL rechazada",
    "SQL_DATABASE_UNAVAILABLE": "Base de datos SQL no disponible",
    "SQL_CONNECTION_TEST_FAILED": "Prueba de conexión SQL falló",
    "SQL_SCHEMA_DISCOVERY_FAILED": "Discovery SQL no disponible",
    "SQL_CONNECTION_DISABLED": "Conexión deshabilitada",
    "SQL_SCOPE_DENIED": "Scope SQL no autorizado",
    "SQL_EXECUTION_FAILED": "Ejecución SQL no disponible",
    "SQL_ALLOWLIST_DENIED": "Objeto SQL fuera de allowlist",
    "SQL_QUERY_INVALID": "Plan SQL inválido",
    "SQL_QUERY_POLICY_BLOCKED": "Plan SQL bloqueado por policy",
}


def _safe_provider_error(exc: Exception, fallback: str) -> EnterpriseSqlError:
    if isinstance(exc, EnterpriseSqlError) and exc.code in _PUBLIC_CONNECTION_ERRORS:
        return EnterpriseSqlError(exc.code, _PUBLIC_CONNECTION_MESSAGES[exc.code])
    return EnterpriseSqlError(fallback, "Operación SQL no disponible")


def _metadata_objects(profile: Dict[str, Any], objects: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    allowed = {str(item).lower() for item in profile.get("allowed_tables") or []}
    safe_objects: List[Dict[str, Any]] = []
    for item in objects:
        schema, name = str(item.get("schema") or ""), str(item.get("name") or "")
        if f"{schema}.{name}".lower() not in allowed:
            continue
        columns = []
        for column in list(item.get("columns") or []):
            columns.append({"name": str(column.get("name") or ""), "type": str(column.get("type") or ""), "nullable": bool(column.get("nullable"))})
        safe_objects.append({"schema": schema, "name": name, "type": str(item.get("type") or ""), "columns": columns})
    return safe_objects


_SMOKE_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,127}$")


def _smoke_identifier(value: Any) -> str:
    text = str(value or "").strip()
    if not _SMOKE_IDENTIFIER.fullmatch(text):
        raise EnterpriseSqlError("SQL_QUERY_INVALID", "Identificador de smoke query inválido")
    return text


def build_smoke_query_plan(profile: Dict[str, Any], request: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(request, dict) or set(request) - {"schema", "object", "columns", "limit"}:
        raise EnterpriseSqlError("SQL_QUERY_INVALID", "Plan estructurado inválido")
    schema, object_name = _smoke_identifier(request.get("schema")), _smoke_identifier(request.get("object"))
    columns = request.get("columns")
    if not isinstance(columns, list) or not columns or any(not isinstance(item, str) for item in columns):
        raise EnterpriseSqlError("SQL_QUERY_INVALID", "columns explícitas son obligatorias")
    names = [_smoke_identifier(item) for item in columns]
    if len(set(names)) != len(names):
        raise EnterpriseSqlError("SQL_QUERY_INVALID", "columns duplicadas no permitidas")
    requested = request.get("limit")
    if isinstance(requested, bool) or not isinstance(requested, int) or requested < 1:
        raise EnterpriseSqlError("SQL_QUERY_INVALID", "limit inválido")
    if schema not in set(profile.get("allowed_schemas") or []) or f"{schema}.{object_name}" not in set(profile.get("allowed_tables") or []):
        raise EnterpriseSqlError("SQL_ALLOWLIST_DENIED", "Objeto SQL fuera de allowlist")
    effective_limit = min(requested, int(profile.get("max_rows") or 500), 5000)
    sql = f"SELECT TOP ({effective_limit}) {', '.join(f'[{name}]' for name in names)} FROM [{schema}].[{object_name}]"
    return {"operation": "SELECT", "sql": sql, "limit": effective_limit, "timeout_seconds": int(profile.get("timeout_seconds") or 30), "parameters": [], "schema": schema, "object": object_name, "selected_columns": names}


def test_connection(store: EnterpriseSqlConnectionStore, provider: Any, scope: Dict[str, Any], connection_id: str) -> Dict[str, Any]:
    profile = assert_sql_profile_active(store.get(scope, connection_id))
    started = time.monotonic()
    try:
        tester = getattr(provider, "test_connection", None)
        if not callable(tester):
            raise EnterpriseSqlError("SQL_CONNECTION_TEST_FAILED", "Provider SQL no permite prueba de conexión")
        tester(profile, int(profile.get("timeout_seconds") or 30))
        elapsed = (time.monotonic() - started) * 1000
        store.record_operation(scope, connection_id, "last_test", "PASS", elapsed)
        return {"status": "PASS", "connection_id": profile["connection_id"], "database": profile["database"], "driver": profile.get("driver"), "authentication_mode": profile.get("auth_mode"), "connection_ms": round(elapsed, 3), "tested_at": datetime.now(timezone.utc).isoformat()}
    except Exception as exc:
        elapsed = (time.monotonic() - started) * 1000
        error = _safe_provider_error(exc, "SQL_CONNECTION_TEST_FAILED")
        store.record_operation(scope, connection_id, "last_test", "FAIL", elapsed, error.code)
        raise error from exc


def discover_schema(store: EnterpriseSqlConnectionStore, provider: SqlServerProvider, scope: Dict[str, Any], connection_id: str) -> Dict[str, Any]:
    profile = assert_sql_profile_active(store.get(scope, connection_id))
    started = time.monotonic()
    try:
        objects = _metadata_objects(profile, provider.discover(profile))
        elapsed = (time.monotonic() - started) * 1000
        store.record_operation(scope, connection_id, "last_discovery", "PASS", elapsed, discovered_object_count=len(objects))
        return {"status": "PASS", "connection_id": profile["connection_id"], "database": profile["database"], "objects": objects, "discovery_ms": round(elapsed, 3), "discovered_at": datetime.now(timezone.utc).isoformat()}
    except Exception as exc:
        elapsed = (time.monotonic() - started) * 1000
        error = _safe_provider_error(exc, "SQL_SCHEMA_DISCOVERY_FAILED")
        store.record_operation(scope, connection_id, "last_discovery", "FAIL", elapsed, error.code)
        raise error from exc


def execute_smoke_query(store: EnterpriseSqlConnectionStore, provider: SqlServerProvider, scope: Dict[str, Any], connection_id: str, request: Dict[str, Any]) -> Dict[str, Any]:
    profile = assert_sql_profile_active(store.get(scope, connection_id))
    plan = build_smoke_query_plan(profile, request)
    started = time.monotonic()
    try:
        result = EnterpriseSqlExecutor(store, provider).execute(scope, connection_id, plan)
        elapsed = (time.monotonic() - started) * 1000
        store.record_operation(scope, connection_id, "last_query", "PASS", elapsed, row_count=result["row_count"])
        provenance = dict(result["provenance"])
        provenance.update({"schema": plan["schema"], "object": plan["object"], "selected_columns": plan["selected_columns"], "query_ms": round(elapsed, 3)})
        return {"status": "PASS", "connection_id": profile["connection_id"], "columns": result["columns"], "rows": result["rows"], "row_count": result["row_count"], "truncated": result["truncated"], "query_ms": round(elapsed, 3), "provenance": provenance}
    except Exception as exc:
        elapsed = (time.monotonic() - started) * 1000
        error = _safe_provider_error(exc, "SQL_EXECUTION_FAILED")
        store.record_operation(scope, connection_id, "last_query", "FAIL", elapsed, error.code)
        raise error from exc


def validate_query_plan(profile: Dict[str, Any], plan: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(plan, dict) or str(plan.get("operation") or "SELECT").upper() != "SELECT": raise EnterpriseSqlError("SQL_QUERY_NOT_READ_ONLY", "Solo SELECT está permitido")
    sql = str(plan.get("sql") or "").strip()
    if not sql: raise EnterpriseSqlError("SQL_QUERY_REQUIRED", "sql es obligatorio en el plan")
    if ";" in sql: raise EnterpriseSqlError("SQL_MULTIPLE_STATEMENTS_BLOCKED", "Solo un statement sin punto y coma")
    if "--" in sql or "/*" in sql or "*/" in sql: raise EnterpriseSqlError("SQL_POLICY_VIOLATION", "Comentarios SQL bloqueados")
    tokens = re.findall(r"[A-Za-z_][A-Za-z0-9_]*", re.sub(r"'(?:''|[^'])*'", "'',", sql).lower())
    if not tokens or tokens[0] != "select": raise EnterpriseSqlError("SQL_QUERY_NOT_READ_ONLY", "La consulta debe iniciar con SELECT")
    if set(tokens) & _FORBIDDEN: raise EnterpriseSqlError("SQL_QUERY_NOT_READ_ONLY", "Comando SQL prohibido")
    if re.search(r"\b(?:from|join)\s+(?:\[[^\]]+\]|[A-Za-z_][A-Za-z0-9_]*)\.(?:\[[^\]]+\]|[A-Za-z_][A-Za-z0-9_]*)\.(?:\[[^\]]+\]|[A-Za-z_][A-Za-z0-9_]*)", sql, flags=re.I): raise EnterpriseSqlError("SQL_DATABASE_NOT_ALLOWED", "Base externa no permitida")
    objects = re.findall(r"\b(?:from|join)\s+((?:\[[^\]]+\]|[A-Za-z_][A-Za-z0-9_]*)\.(?:\[[^\]]+\]|[A-Za-z_][A-Za-z0-9_]*))(?!\.)", sql, flags=re.I)
    if not objects: raise EnterpriseSqlError("SQL_POLICY_VIOLATION", "Se requiere objeto schema.table permitido")
    normalized = [item.replace("[", "").replace("]", "") for item in objects]
    allowed = {str(x).lower() for x in profile.get("allowed_tables") or []}
    if any(item.lower() not in allowed for item in normalized): raise EnterpriseSqlError("SQL_OBJECT_NOT_ALLOWED", "Objeto SQL fuera de allowlist")
    if re.search(r"\b(?:from|join)\s+(?:\w+\.){2,}", sql, flags=re.I): raise EnterpriseSqlError("SQL_DATABASE_NOT_ALLOWED", "Base externa no permitida")
    limit = plan.get("limit", 500); timeout = plan.get("timeout_seconds", 30)
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1: raise EnterpriseSqlError("SQL_QUERY_LIMIT_EXCEEDED", "Límite inválido")
    if isinstance(timeout, bool) or not isinstance(timeout, int) or not 1 <= timeout <= 120: raise EnterpriseSqlError("SQL_TIMEOUT", "Timeout inválido")
    return {"sql": sql, "objects": normalized, "limit": min(limit, 5000), "timeout_seconds": timeout, "parameters": list(plan.get("parameters") or []), "query_fingerprint_sha256": hashlib.sha256(_canonical({"sql": sql, "parameters": list(plan.get("parameters") or []), "objects": normalized})).hexdigest()}


class EnterpriseSqlExecutor:
    def __init__(self, store: EnterpriseSqlConnectionStore, provider: SqlServerProvider): self.store, self.provider = store, provider
    def discover(self, scope: Dict[str, Any], connection_id: str) -> Dict[str, Any]:
        profile = self.store.get(scope, connection_id)
        if not profile.get("enabled") or not profile.get("read_only"): raise EnterpriseSqlError("SQL_POLICY_VIOLATION", "Conexión no habilitada read-only")
        allowed = {x.lower() for x in profile["allowed_tables"]}; objects = []
        for item in self.provider.discover(profile):
            name = f"{item.get('schema')}.{item.get('name')}".lower()
            if name in allowed: objects.append(item)
        return {"connection_id": profile["connection_id"], "database": profile["database"], "objects": objects, "provenance": {"provider": "sqlserver", "scope": profile["scope"], "policy_version": ENTERPRISE_SQL_GATEWAY_VERSION}}
    def execute(self, scope: Dict[str, Any], connection_id: str, plan: Dict[str, Any]) -> Dict[str, Any]:
        profile = self.store.get(scope, connection_id)
        if not profile.get("enabled") or not profile.get("read_only"): raise EnterpriseSqlError("SQL_POLICY_VIOLATION", "Conexión no habilitada read-only")
        valid = validate_query_plan(profile, plan)
        try: raw = self.provider.execute(profile, valid["sql"], valid["parameters"], valid["timeout_seconds"])
        except EnterpriseSqlError: raise
        except Exception as exc: raise EnterpriseSqlError("SQL_EXECUTION_FAILED", "Ejecución SQL falló") from exc
        rows = list(raw.get("rows") or []); truncated = len(rows) > valid["limit"]; rows = rows[:valid["limit"]]
        return {"status": "ANSWERED", "columns": list(raw.get("columns") or []), "rows": rows, "row_count": len(rows), "truncated": truncated, "provenance": {"scope": profile["scope"], "connection_id": profile["connection_id"], "database": profile["database"], "objects": valid["objects"], "query_fingerprint_sha256": valid["query_fingerprint_sha256"], "executed_at": datetime.now(timezone.utc).isoformat(), "provider": "sqlserver", "policy_version": ENTERPRISE_SQL_GATEWAY_VERSION, "timeout_seconds": valid["timeout_seconds"]}}
