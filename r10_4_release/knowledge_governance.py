from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

from .database import Database, utcnow
from .security import Principal, scope_clause

VALID_STATUSES = {"PROPUESTO", "VALIDADO", "RECHAZADO", "OBSOLETO"}
VALID_SCOPES = {"company", "user"}

SCHEMA = r"""
CREATE TABLE IF NOT EXISTS semantic_definitions (
    id TEXT PRIMARY KEY,
    company_id TEXT NOT NULL,
    user_id TEXT,
    scope TEXT NOT NULL DEFAULT 'company',
    physical_name TEXT NOT NULL,
    semantic_name TEXT NOT NULL,
    data_type TEXT,
    unit TEXT,
    description TEXT,
    area TEXT,
    source_type TEXT,
    source_ref TEXT,
    confidence REAL NOT NULL DEFAULT 0.7,
    status TEXT NOT NULL DEFAULT 'PROPUESTO',
    version INTEGER NOT NULL DEFAULT 1,
    valid_from TEXT,
    valid_to TEXT,
    supersedes_id TEXT,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_semantic_scope
ON semantic_definitions(company_id,user_id,scope,active,status,physical_name);
CREATE INDEX IF NOT EXISTS idx_semantic_concept
ON semantic_definitions(company_id,semantic_name,active,status);

CREATE TABLE IF NOT EXISTS business_rules (
    id TEXT PRIMARY KEY,
    company_id TEXT NOT NULL,
    user_id TEXT,
    scope TEXT NOT NULL DEFAULT 'company',
    name TEXT NOT NULL,
    area TEXT,
    expression TEXT NOT NULL,
    description TEXT,
    source_type TEXT,
    source_ref TEXT,
    confidence REAL NOT NULL DEFAULT 0.7,
    status TEXT NOT NULL DEFAULT 'PROPUESTO',
    version INTEGER NOT NULL DEFAULT 1,
    valid_from TEXT,
    valid_to TEXT,
    supersedes_id TEXT,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_rule_scope
ON business_rules(company_id,user_id,scope,active,status,name);
CREATE INDEX IF NOT EXISTS idx_rule_area
ON business_rules(company_id,area,active,status);

CREATE TABLE IF NOT EXISTS knowledge_governance_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    object_type TEXT NOT NULL,
    object_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    snapshot_json TEXT NOT NULL,
    changed_by TEXT,
    changed_at TEXT NOT NULL,
    reason TEXT
);
"""


def _iso_day(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    raw = str(value).strip()
    try:
        return date.fromisoformat(raw[:10]).isoformat()
    except Exception as exc:
        raise ValueError(f"Fecha invalida: {value}") from exc


def _row_dict(row) -> Dict[str, Any]:
    data = dict(row)
    data["active"] = bool(data.get("active"))
    return data


def _overlaps(a_from: Optional[str], a_to: Optional[str], b_from: Optional[str], b_to: Optional[str]) -> bool:
    lo_a = a_from or "0001-01-01"
    hi_a = a_to or "9999-12-31"
    lo_b = b_from or "0001-01-01"
    hi_b = b_to or "9999-12-31"
    return lo_a <= hi_b and lo_b <= hi_a


class KnowledgeGovernance:
    """Gobernanza persistente y auditable para reglas y diccionario empresarial.

    No reemplaza MemoryManager. Complementa la memoria libre con entidades que
    necesitan estado, vigencia, versionado, aislamiento y deteccion de conflictos.
    """

    def __init__(self, db: Database):
        self.db = db
        self.ensure_schema()

    def ensure_schema(self) -> None:
        with self.db.tx() as con:
            con.executescript(SCHEMA)

    def _snapshot(self, table: str, object_type: str, object_id: str, changed_by: str, reason: str) -> None:
        row = self.db.one(f"SELECT * FROM {table} WHERE id=?", (object_id,))
        if not row:
            return
        self.db.execute(
            "INSERT INTO knowledge_governance_history(object_type,object_id,version,snapshot_json,changed_by,changed_at,reason) VALUES(?,?,?,?,?,?,?)",
            (object_type, object_id, int(row["version"]), json.dumps(dict(row), ensure_ascii=False), changed_by, utcnow(), reason),
        )

    @staticmethod
    def _owner(principal: Principal, scope: str) -> Optional[str]:
        if scope not in VALID_SCOPES:
            raise ValueError("scope invalido")
        return principal.user_id if scope == "user" else None

    def propose_rule(
        self,
        principal: Principal,
        *,
        name: str,
        expression: str,
        area: Optional[str] = None,
        description: Optional[str] = None,
        scope: str = "company",
        source_type: str = "user",
        source_ref: Optional[str] = None,
        confidence: float = 0.7,
        valid_from: Optional[str] = None,
        valid_to: Optional[str] = None,
        supersedes_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not str(name).strip() or not str(expression).strip():
            raise ValueError("name y expression son obligatorios")
        owner = self._owner(principal, scope)
        vf, vt = _iso_day(valid_from), _iso_day(valid_to)
        if vf and vt and vf > vt:
            raise ValueError("valid_from no puede ser posterior a valid_to")
        rule_id = str(uuid.uuid4())
        now = utcnow()
        self.db.execute(
            "INSERT INTO business_rules(id,company_id,user_id,scope,name,area,expression,description,source_type,source_ref,confidence,status,version,valid_from,valid_to,supersedes_id,active,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (rule_id, principal.company_id, owner, scope, str(name).strip(), area, str(expression).strip(), description,
             source_type, source_ref, float(confidence), "PROPUESTO", 1, vf, vt, supersedes_id, 1, now, now),
        )
        self._snapshot("business_rules", "business_rule", rule_id, principal.user_id, "create_proposal")
        self.db.audit("knowledge.rule.propose", principal.company_id, principal.user_id, "business_rule", rule_id,
                      details={"name": str(name).strip(), "area": area, "scope": scope})
        return self.get_rule(principal, rule_id, include_nonvalidated=True)

    def get_rule(self, principal: Principal, rule_id: str, include_nonvalidated: bool = False) -> Dict[str, Any]:
        clause, args = scope_clause(principal)
        row = self.db.one(f"SELECT * FROM business_rules WHERE id=? AND {clause}", (rule_id, *args))
        if not row or (not include_nonvalidated and (row["status"] != "VALIDADO" or not row["active"])):
            raise KeyError("Regla no encontrada")
        return _row_dict(row)

    def list_rules(self, principal: Principal, *, status: Optional[str] = None, area: Optional[str] = None, include_inactive: bool = False) -> List[Dict[str, Any]]:
        clause, args = scope_clause(principal)
        sql = f"SELECT * FROM business_rules WHERE {clause}"
        params = list(args)
        if not include_inactive:
            sql += " AND active=1"
        if status:
            status = status.upper()
            if status not in VALID_STATUSES:
                raise ValueError("status invalido")
            sql += " AND status=?"
            params.append(status)
        if area:
            sql += " AND area=?"
            params.append(area)
        sql += " ORDER BY name,version DESC,updated_at DESC"
        return [_row_dict(r) for r in self.db.query(sql, params)]

    def detect_rule_conflicts(self, principal: Principal, rule_id: str) -> List[Dict[str, Any]]:
        candidate = self.get_rule(principal, rule_id, include_nonvalidated=True)
        conflicts = []
        for row in self.list_rules(principal, status="VALIDADO"):
            if row["id"] == rule_id or str(row["name"]).strip().lower() != str(candidate["name"]).strip().lower():
                continue
            if not _overlaps(candidate.get("valid_from"), candidate.get("valid_to"), row.get("valid_from"), row.get("valid_to")):
                continue
            if str(row["expression"]).strip() != str(candidate["expression"]).strip():
                conflicts.append(row)
        return conflicts

    def validate_rule(self, principal: Principal, rule_id: str, *, replace_conflicts: bool = False) -> Dict[str, Any]:
        current = self.get_rule(principal, rule_id, include_nonvalidated=True)
        if current["status"] == "RECHAZADO":
            raise ValueError("Una regla rechazada no puede validarse; cree una nueva propuesta")
        conflicts = self.detect_rule_conflicts(principal, rule_id)
        if conflicts and not replace_conflicts:
            raise ValueError("CONFLICTO: existe una regla VALIDADA con el mismo nombre y vigencia superpuesta")
        self._snapshot("business_rules", "business_rule", rule_id, principal.user_id, "validate")
        if replace_conflicts:
            for old in conflicts:
                self._snapshot("business_rules", "business_rule", old["id"], principal.user_id, "superseded")
                self.db.execute("UPDATE business_rules SET status='OBSOLETO',active=0,version=version+1,updated_at=? WHERE id=?", (utcnow(), old["id"]))
        self.db.execute(
            "UPDATE business_rules SET status='VALIDADO',active=1,confidence=CASE WHEN confidence<0.8 THEN 0.8 ELSE confidence END,version=version+1,updated_at=? WHERE id=?",
            (utcnow(), rule_id),
        )
        self.db.audit("knowledge.rule.validate", principal.company_id, principal.user_id, "business_rule", rule_id,
                      details={"replaced_conflicts": len(conflicts) if replace_conflicts else 0})
        return self.get_rule(principal, rule_id)

    def reject_rule(self, principal: Principal, rule_id: str) -> Dict[str, Any]:
        self.get_rule(principal, rule_id, include_nonvalidated=True)
        self._snapshot("business_rules", "business_rule", rule_id, principal.user_id, "reject")
        self.db.execute("UPDATE business_rules SET status='RECHAZADO',active=0,version=version+1,updated_at=? WHERE id=?", (utcnow(), rule_id))
        self.db.audit("knowledge.rule.reject", principal.company_id, principal.user_id, "business_rule", rule_id)
        return self.get_rule(principal, rule_id, include_nonvalidated=True)

    def obsolete_rule(self, principal: Principal, rule_id: str) -> Dict[str, Any]:
        self.get_rule(principal, rule_id, include_nonvalidated=True)
        self._snapshot("business_rules", "business_rule", rule_id, principal.user_id, "obsolete")
        self.db.execute("UPDATE business_rules SET status='OBSOLETO',active=0,version=version+1,updated_at=? WHERE id=?", (utcnow(), rule_id))
        self.db.audit("knowledge.rule.obsolete", principal.company_id, principal.user_id, "business_rule", rule_id)
        return self.get_rule(principal, rule_id, include_nonvalidated=True)

    def applicable_rules(self, principal: Principal, *, area: Optional[str] = None, on_date: Optional[str] = None) -> List[Dict[str, Any]]:
        target = _iso_day(on_date) or datetime.now(timezone.utc).date().isoformat()
        out = []
        for row in self.list_rules(principal, status="VALIDADO", area=area):
            if row.get("valid_from") and row["valid_from"] > target:
                continue
            if row.get("valid_to") and row["valid_to"] < target:
                continue
            out.append(row)
        return out

    def propose_semantic_definition(
        self,
        principal: Principal,
        *,
        physical_name: str,
        semantic_name: str,
        data_type: Optional[str] = None,
        unit: Optional[str] = None,
        description: Optional[str] = None,
        area: Optional[str] = None,
        scope: str = "company",
        source_type: str = "inference",
        source_ref: Optional[str] = None,
        confidence: float = 0.6,
        valid_from: Optional[str] = None,
        valid_to: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not str(physical_name).strip() or not str(semantic_name).strip():
            raise ValueError("physical_name y semantic_name son obligatorios")
        owner = self._owner(principal, scope)
        vf, vt = _iso_day(valid_from), _iso_day(valid_to)
        item_id = str(uuid.uuid4())
        now = utcnow()
        self.db.execute(
            "INSERT INTO semantic_definitions(id,company_id,user_id,scope,physical_name,semantic_name,data_type,unit,description,area,source_type,source_ref,confidence,status,version,valid_from,valid_to,supersedes_id,active,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (item_id, principal.company_id, owner, scope, str(physical_name).strip(), str(semantic_name).strip(), data_type, unit,
             description, area, source_type, source_ref, float(confidence), "PROPUESTO", 1, vf, vt, None, 1, now, now),
        )
        self._snapshot("semantic_definitions", "semantic_definition", item_id, principal.user_id, "create_proposal")
        self.db.audit("knowledge.semantic.propose", principal.company_id, principal.user_id, "semantic_definition", item_id,
                      details={"physical_name": str(physical_name).strip(), "semantic_name": str(semantic_name).strip(), "area": area})
        return self.get_semantic_definition(principal, item_id, include_nonvalidated=True)

    def get_semantic_definition(self, principal: Principal, item_id: str, include_nonvalidated: bool = False) -> Dict[str, Any]:
        clause, args = scope_clause(principal)
        row = self.db.one(f"SELECT * FROM semantic_definitions WHERE id=? AND {clause}", (item_id, *args))
        if not row or (not include_nonvalidated and (row["status"] != "VALIDADO" or not row["active"])):
            raise KeyError("Definicion semantica no encontrada")
        return _row_dict(row)

    def list_semantic_definitions(self, principal: Principal, *, status: Optional[str] = None, physical_name: Optional[str] = None, include_inactive: bool = False) -> List[Dict[str, Any]]:
        clause, args = scope_clause(principal)
        sql = f"SELECT * FROM semantic_definitions WHERE {clause}"
        params = list(args)
        if not include_inactive:
            sql += " AND active=1"
        if status:
            status = status.upper()
            if status not in VALID_STATUSES:
                raise ValueError("status invalido")
            sql += " AND status=?"
            params.append(status)
        if physical_name:
            sql += " AND lower(physical_name)=lower(?)"
            params.append(physical_name)
        sql += " ORDER BY physical_name,version DESC,updated_at DESC"
        return [_row_dict(r) for r in self.db.query(sql, params)]

    def detect_semantic_conflicts(self, principal: Principal, item_id: str) -> List[Dict[str, Any]]:
        candidate = self.get_semantic_definition(principal, item_id, include_nonvalidated=True)
        conflicts = []
        for row in self.list_semantic_definitions(principal, status="VALIDADO", physical_name=candidate["physical_name"]):
            if row["id"] == item_id:
                continue
            if not _overlaps(candidate.get("valid_from"), candidate.get("valid_to"), row.get("valid_from"), row.get("valid_to")):
                continue
            if str(row["semantic_name"]).strip().lower() != str(candidate["semantic_name"]).strip().lower():
                conflicts.append(row)
        return conflicts

    def validate_semantic_definition(self, principal: Principal, item_id: str, *, replace_conflicts: bool = False) -> Dict[str, Any]:
        current = self.get_semantic_definition(principal, item_id, include_nonvalidated=True)
        if current["status"] == "RECHAZADO":
            raise ValueError("Una definicion rechazada no puede validarse; cree una nueva propuesta")
        conflicts = self.detect_semantic_conflicts(principal, item_id)
        if conflicts and not replace_conflicts:
            raise ValueError("CONFLICTO: existe una definicion VALIDADA incompatible para el mismo campo y vigencia")
        self._snapshot("semantic_definitions", "semantic_definition", item_id, principal.user_id, "validate")
        if replace_conflicts:
            for old in conflicts:
                self._snapshot("semantic_definitions", "semantic_definition", old["id"], principal.user_id, "superseded")
                self.db.execute("UPDATE semantic_definitions SET status='OBSOLETO',active=0,version=version+1,updated_at=? WHERE id=?", (utcnow(), old["id"]))
        self.db.execute(
            "UPDATE semantic_definitions SET status='VALIDADO',active=1,confidence=CASE WHEN confidence<0.8 THEN 0.8 ELSE confidence END,version=version+1,updated_at=? WHERE id=?",
            (utcnow(), item_id),
        )
        self.db.audit("knowledge.semantic.validate", principal.company_id, principal.user_id, "semantic_definition", item_id,
                      details={"replaced_conflicts": len(conflicts) if replace_conflicts else 0})
        return self.get_semantic_definition(principal, item_id)

    def reject_semantic_definition(self, principal: Principal, item_id: str) -> Dict[str, Any]:
        self.get_semantic_definition(principal, item_id, include_nonvalidated=True)
        self._snapshot("semantic_definitions", "semantic_definition", item_id, principal.user_id, "reject")
        self.db.execute("UPDATE semantic_definitions SET status='RECHAZADO',active=0,version=version+1,updated_at=? WHERE id=?", (utcnow(), item_id))
        self.db.audit("knowledge.semantic.reject", principal.company_id, principal.user_id, "semantic_definition", item_id)
        return self.get_semantic_definition(principal, item_id, include_nonvalidated=True)

    def resolve_semantic(self, principal: Principal, physical_name: str, *, on_date: Optional[str] = None) -> Optional[Dict[str, Any]]:
        target = _iso_day(on_date) or datetime.now(timezone.utc).date().isoformat()
        rows = self.list_semantic_definitions(principal, status="VALIDADO", physical_name=physical_name)
        valid = [r for r in rows if (not r.get("valid_from") or r["valid_from"] <= target) and (not r.get("valid_to") or r["valid_to"] >= target)]
        if not valid:
            return None
        valid.sort(key=lambda r: (int(r.get("version") or 1), str(r.get("updated_at") or "")), reverse=True)
        return valid[0]

    def provenance(self, principal: Principal, object_type: str, object_id: str) -> Dict[str, Any]:
        if object_type == "business_rule":
            current = self.get_rule(principal, object_id, include_nonvalidated=True)
        elif object_type == "semantic_definition":
            current = self.get_semantic_definition(principal, object_id, include_nonvalidated=True)
        else:
            raise ValueError("object_type invalido")
        history = [dict(r) for r in self.db.query(
            "SELECT version,changed_by,changed_at,reason FROM knowledge_governance_history WHERE object_type=? AND object_id=? ORDER BY id",
            (object_type, object_id),
        )]
        return {"current": current, "history": history}
