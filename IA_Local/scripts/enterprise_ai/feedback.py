from __future__ import annotations

import json
import re
import uuid
from typing import Any, Dict, List, Optional

from .database import Database, utcnow
from .security import Principal, scope_clause

FEEDBACK_TYPES = {"CORRECTO", "REQUIERE_CORRECCION"}
PROPOSAL_TYPES = {"none", "memory", "rule", "semantic"}
FEEDBACK_STATUSES = {"RECIBIDO", "PROPUESTO", "VALIDADO", "RECHAZADO"}

SCHEMA = r"""
CREATE TABLE IF NOT EXISTS feedback_events (
    id TEXT PRIMARY KEY,
    company_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    feedback_type TEXT NOT NULL,
    target_type TEXT,
    target_ref TEXT,
    area TEXT,
    original_text TEXT,
    correction_text TEXT,
    proposal_type TEXT NOT NULL DEFAULT 'none',
    proposal_object_id TEXT,
    proposal_status TEXT NOT NULL DEFAULT 'RECIBIDO',
    source_context_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_feedback_scope
ON feedback_events(company_id,user_id,created_at);
CREATE INDEX IF NOT EXISTS idx_feedback_proposal
ON feedback_events(company_id,proposal_type,proposal_status,created_at);

CREATE TABLE IF NOT EXISTS feedback_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    feedback_id TEXT NOT NULL,
    snapshot_json TEXT NOT NULL,
    changed_by TEXT,
    changed_at TEXT NOT NULL,
    reason TEXT
);
"""

class FeedbackManager:
    """Feedback controlado: registra correcciones y propone conocimiento sin validarlo automaticamente."""

    def __init__(self, db: Database, memory=None, governance=None):
        self.db = db
        self.memory = memory
        self.governance = governance
        self.ensure_schema()

    def ensure_schema(self) -> None:
        with self.db.tx() as con:
            con.executescript(SCHEMA)

    def _snapshot(self, feedback_id: str, principal: Principal, reason: str) -> None:
        row = self.db.one("SELECT * FROM feedback_events WHERE id=? AND company_id=? AND user_id=?", (feedback_id, principal.company_id, principal.user_id))
        if row:
            self.db.execute(
                "INSERT INTO feedback_history(feedback_id,snapshot_json,changed_by,changed_at,reason) VALUES(?,?,?,?,?)",
                (feedback_id, json.dumps(dict(row), ensure_ascii=False), principal.user_id, utcnow(), reason),
            )

    @staticmethod
    def _row(row) -> Dict[str, Any]:
        data = dict(row)
        try:
            data["source_context"] = json.loads(data.pop("source_context_json") or "{}")
        except Exception:
            data["source_context"] = {}
        return data

    @staticmethod
    def _detect_proposal_type(correction: str) -> str:
        text = (correction or "").strip()
        low = text.lower()
        if re.search(r"\b(?:significa|equivale a|corresponde a)\b", low) or "->" in text or "→" in text:
            return "semantic"
        if "=" in text or re.search(r"\b(?:se calcula|debe calcular|regla|para nosotros|solo es valida|sólo es válida|venta valida|venta válida)\b", low):
            return "rule"
        return "memory"

    @staticmethod
    def _semantic_parts(correction: str) -> tuple[Optional[str], Optional[str]]:
        text = (correction or "").strip()
        for sep in ("->", "→"):
            if sep in text:
                a,b = text.split(sep,1)
                return a.strip() or None, b.strip() or None
        m = re.search(r"^\s*(.+?)\s+(?:significa|equivale a|corresponde a)\s+(.+?)\s*$", text, flags=re.I)
        return (m.group(1).strip(), m.group(2).strip()) if m else (None,None)

    def submit(
        self,
        principal: Principal,
        *,
        feedback_type: str,
        target_type: Optional[str] = None,
        target_ref: Optional[str] = None,
        area: Optional[str] = None,
        original_text: Optional[str] = None,
        correction_text: Optional[str] = None,
        proposal_type: str = "auto",
        source_context: Optional[Dict[str, Any]] = None,
        proposal_name: Optional[str] = None,
        physical_name: Optional[str] = None,
        semantic_name: Optional[str] = None,
        valid_from: Optional[str] = None,
        valid_to: Optional[str] = None,
        scope: str = "company",
    ) -> Dict[str, Any]:
        ftype = str(feedback_type or "").strip().upper()
        if ftype not in FEEDBACK_TYPES:
            raise ValueError("feedback_type invalido")
        correction = (correction_text or "").strip()
        if ftype == "REQUIERE_CORRECCION" and not correction:
            raise ValueError("La correccion es obligatoria")
        ptype = str(proposal_type or "auto").strip().lower()
        if ftype == "CORRECTO":
            ptype = "none"
        elif ptype == "auto":
            ptype = self._detect_proposal_type(correction)
        if ptype not in PROPOSAL_TYPES:
            raise ValueError("proposal_type invalido")

        fid = str(uuid.uuid4()); now = utcnow()
        self.db.execute(
            "INSERT INTO feedback_events(id,company_id,user_id,feedback_type,target_type,target_ref,area,original_text,correction_text,proposal_type,proposal_object_id,proposal_status,source_context_json,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (fid, principal.company_id, principal.user_id, ftype, target_type, target_ref, area, original_text, correction or None, ptype, None,
             "RECIBIDO", json.dumps(source_context or {}, ensure_ascii=False), now, now),
        )
        self._snapshot(fid, principal, "create")

        proposal = None
        if ftype == "REQUIERE_CORRECCION" and ptype != "none":
            source_ref = f"feedback:{fid}"
            if ptype == "rule":
                if not self.governance:
                    raise RuntimeError("Gobernanza no disponible")
                name = (proposal_name or "REGLA_PROPUESTA_DESDE_FEEDBACK").strip()
                proposal = self.governance.propose_rule(
                    principal, name=name, expression=correction, area=area, description="Propuesta originada por correccion del usuario",
                    scope=scope, source_type="feedback", source_ref=source_ref, confidence=0.75,
                    valid_from=valid_from, valid_to=valid_to,
                )
                proposal_id = proposal["id"]
            elif ptype == "semantic":
                if not self.governance:
                    raise RuntimeError("Gobernanza no disponible")
                physical = (physical_name or "").strip(); semantic = (semantic_name or "").strip()
                if not physical or not semantic:
                    p,s = self._semantic_parts(correction); physical = physical or (p or ""); semantic = semantic or (s or "")
                if not physical or not semantic:
                    raise ValueError("Una propuesta semantica requiere physical_name y semantic_name")
                proposal = self.governance.propose_semantic_definition(
                    principal, physical_name=physical, semantic_name=semantic, description="Propuesta originada por correccion del usuario",
                    area=area, scope=scope, source_type="feedback", source_ref=source_ref, confidence=0.75,
                    valid_from=valid_from, valid_to=valid_to,
                )
                proposal_id = proposal["id"]
            else:
                if not self.memory:
                    raise RuntimeError("Memoria no disponible")
                proposal = self.memory.create(
                    principal, correction, "conocimiento_empresa", scope=scope, source_type="feedback", source_ref=source_ref,
                    confidence=0.7, importance=0.7, tags=["feedback","correccion"], status="pending",
                )
                proposal_id = proposal["id"]
            self.db.execute("UPDATE feedback_events SET proposal_object_id=?,proposal_status='PROPUESTO',updated_at=? WHERE id=?", (proposal_id, utcnow(), fid))
            self._snapshot(fid, principal, "proposal_created")

        self.db.audit("feedback.submit", principal.company_id, principal.user_id, "feedback", fid,
                      details={"feedback_type": ftype, "proposal_type": ptype, "target_type": target_type})
        out = self.get(principal, fid)
        out["proposal"] = proposal
        return out

    def get(self, principal: Principal, feedback_id: str) -> Dict[str, Any]:
        row = self.db.one("SELECT * FROM feedback_events WHERE id=? AND company_id=? AND user_id=?", (feedback_id, principal.company_id, principal.user_id))
        if not row:
            raise KeyError("Feedback no encontrado")
        return self._row(row)

    def list(self, principal: Principal, *, limit: int = 100) -> List[Dict[str, Any]]:
        rows = self.db.query("SELECT * FROM feedback_events WHERE company_id=? AND user_id=? ORDER BY created_at DESC LIMIT ?", (principal.company_id, principal.user_id, max(1,min(int(limit),500))))
        return [self._row(r) for r in rows]

    def validate_proposal(self, principal: Principal, feedback_id: str, *, replace_conflicts: bool = False) -> Dict[str, Any]:
        item = self.get(principal, feedback_id)
        if item["proposal_status"] != "PROPUESTO" or not item.get("proposal_object_id"):
            raise ValueError("El feedback no tiene una propuesta pendiente")
        ptype = item["proposal_type"]; oid = item["proposal_object_id"]
        if ptype == "rule":
            result = self.governance.validate_rule(principal, oid, replace_conflicts=replace_conflicts)
        elif ptype == "semantic":
            result = self.governance.validate_semantic_definition(principal, oid, replace_conflicts=replace_conflicts)
        elif ptype == "memory":
            result = self.memory.confirm(principal, oid)
        else:
            raise ValueError("Tipo de propuesta no validable")
        self._snapshot(feedback_id, principal, "validate_proposal")
        self.db.execute("UPDATE feedback_events SET proposal_status='VALIDADO',updated_at=? WHERE id=?", (utcnow(), feedback_id))
        self.db.audit("feedback.validate", principal.company_id, principal.user_id, "feedback", feedback_id,
                      details={"proposal_type": ptype, "proposal_object_id": oid})
        out = self.get(principal, feedback_id); out["validated_object"] = result
        return out

    def reject_proposal(self, principal: Principal, feedback_id: str) -> Dict[str, Any]:
        item = self.get(principal, feedback_id)
        if item["proposal_status"] != "PROPUESTO" or not item.get("proposal_object_id"):
            raise ValueError("El feedback no tiene una propuesta pendiente")
        ptype = item["proposal_type"]; oid = item["proposal_object_id"]
        if ptype == "rule": self.governance.reject_rule(principal, oid)
        elif ptype == "semantic": self.governance.reject_semantic_definition(principal, oid)
        elif ptype == "memory": self.memory.forget(principal, oid)
        self._snapshot(feedback_id, principal, "reject_proposal")
        self.db.execute("UPDATE feedback_events SET proposal_status='RECHAZADO',updated_at=? WHERE id=?", (utcnow(), feedback_id))
        self.db.audit("feedback.reject", principal.company_id, principal.user_id, "feedback", feedback_id,
                      details={"proposal_type": ptype, "proposal_object_id": oid})
        return self.get(principal, feedback_id)

    def provenance(self, principal: Principal, feedback_id: str) -> Dict[str, Any]:
        current = self.get(principal, feedback_id)
        hist = [dict(r) for r in self.db.query("SELECT snapshot_json,changed_by,changed_at,reason FROM feedback_history WHERE feedback_id=? ORDER BY id", (feedback_id,))]
        return {"current": current, "history": hist}
