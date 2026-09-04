from __future__ import annotations

import hashlib
import json
import re
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
    return {key:record.get(key) for key in ("connection_id","server","database","auth_mode","driver","timeout_seconds","max_rows","trust_server_certificate","allowed_schemas","allowed_tables","enabled","display_name","secret_reference","created_at","updated_at")}


class SqlServerProvider(Protocol):
    def discover(self, profile: Dict[str, Any]) -> List[Dict[str, Any]]: ...
    def execute(self, profile: Dict[str, Any], sql: str, parameters: List[Any], timeout_seconds: int) -> Dict[str, Any]: ...


class SqlServerPyodbcProvider:
    """Provider SQL Server opcional; el secret sólo se resuelve en runtime."""
    def _connect(self, profile: Dict[str, Any], timeout_seconds: int):
        try:
            import pyodbc
        except ImportError as exc:
            raise EnterpriseSqlError("SQL_DRIVER_NOT_AVAILABLE", "Driver SQL Server no disponible") from exc
        import os
        ref = str(profile.get("credential_ref") or "")
        secret = os.environ.get(ref[4:]) if ref.startswith("env:") else None
        if not secret:
            raise EnterpriseSqlError("SQL_CREDENTIAL_UNAVAILABLE", "Credencial SQL no disponible")
        try:
            return pyodbc.connect(secret, timeout=timeout_seconds, autocommit=False)
        except Exception as exc:
            raise EnterpriseSqlError("SQL_EXECUTION_FAILED", "No fue posible abrir la conexión SQL") from exc
    def discover(self, profile: Dict[str, Any]) -> List[Dict[str, Any]]:
        conn = self._connect(profile, 30)
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
        except Exception as exc: raise EnterpriseSqlError("SQL_SCHEMA_NOT_AVAILABLE", "Metadata SQL no disponible") from exc
        finally:
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
    def register(self, *, scope: Dict[str, Any], connection_id: str, server: str, database: str, auth_mode: str, credential_ref: str = "", allowed_schemas: List[str]=None, allowed_tables: List[str]=None, enabled: bool = True, display_name: str="", driver: str="ODBC Driver 18 for SQL Server", timeout_seconds:int=30, max_rows:int=500, trust_server_certificate:bool=False, secret_reference:str="") -> Dict[str, Any]:
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
        record = {"schema_version": ENTERPRISE_SQL_GATEWAY_VERSION, "connection_id": _safe(connection_id, "SQL_CONNECTION_INVALID"), "scope": s, "provider": "sqlserver", "server": str(server).strip(), "database": str(database).strip(), "auth_mode":mode, "credential_ref": str(credential_ref).strip(), "secret_reference":str(secret_reference or credential_ref).strip() or None, "allowed_schemas": schemas, "allowed_tables": tables, "read_only": True, "enabled": bool(enabled), "display_name":str(display_name).strip() or None,"driver":driver,"timeout_seconds":timeout_seconds,"max_rows":max_rows,"trust_server_certificate":bool(trust_server_certificate),"created_at": datetime.now(timezone.utc).isoformat(),"updated_at":datetime.now(timezone.utc).isoformat()}
        record["fingerprint_sha256"] = _fingerprint(record); path.write_bytes(_canonical(record)); return dict(record)
    def get(self, scope: Dict[str, Any], connection_id: str) -> Dict[str, Any]:
        path = self._path(scope, connection_id)
        if not path.is_file(): raise EnterpriseSqlError("SQL_CONNECTION_NOT_FOUND", "Conexión SQL no encontrada")
        return self._read(path)
    def list(self, scope: Dict[str, Any]) -> List[Dict[str, Any]]:
        directory = self._dir(scope)
        return [] if not directory.exists() else [self._read(p) for p in sorted(directory.glob("*.json"))]
    def update(self, scope: Dict[str,Any], connection_id: str, **changes) -> Dict[str,Any]:
        record=self.get(scope,connection_id); allowed={"display_name","server","database","driver","timeout_seconds","max_rows","trust_server_certificate","allowed_schemas","allowed_tables","secret_reference"}
        if set(changes)-allowed: raise EnterpriseSqlError("SQL_CONNECTION_PROFILE_INVALID","Campo administrativo no permitido")
        if "timeout_seconds" in changes and (isinstance(changes["timeout_seconds"],bool) or not 1<=int(changes["timeout_seconds"])<=120): raise EnterpriseSqlError("SQL_CONNECTION_PROFILE_INVALID","Timeout inválido")
        if "max_rows" in changes and (isinstance(changes["max_rows"],bool) or not 1<=int(changes["max_rows"])<=5000): raise EnterpriseSqlError("SQL_CONNECTION_PROFILE_INVALID","max_rows inválido")
        for key,value in changes.items(): record[key]=value
        record["updated_at"]=datetime.now(timezone.utc).isoformat(); record["fingerprint_sha256"]=_fingerprint(record); self._path(scope,connection_id).write_bytes(_canonical(record)); return dict(record)
    def disable(self,scope:Dict[str,Any],connection_id:str)->Dict[str,Any]:
        record=self.update(scope,connection_id);record["enabled"]=False;record["status"]="DISABLED";record["updated_at"]=datetime.now(timezone.utc).isoformat();record["fingerprint_sha256"]=_fingerprint(record);self._path(scope,connection_id).write_bytes(_canonical(record));return record
    def enable(self,scope:Dict[str,Any],connection_id:str)->Dict[str,Any]:
        record=self.update(scope,connection_id);record["enabled"]=True;record["status"]="ACTIVE";record["updated_at"]=datetime.now(timezone.utc).isoformat();record["fingerprint_sha256"]=_fingerprint(record);self._path(scope,connection_id).write_bytes(_canonical(record));return record

def assert_sql_profile_active(profile:Dict[str,Any])->Dict[str,Any]:
    if not profile.get("enabled",True) or profile.get("status")=="DISABLED": raise EnterpriseSqlError("SQL_CONNECTION_DISABLED","Conexión deshabilitada")
    return profile


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
