from __future__ import annotations

import json
import re
import uuid
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

from .database import Database, utcnow
from .providers import EmbeddingProvider
from .security import Principal, scope_clause
from .vector_store import VectorStore

CATEGORIES = {
    "regla_negocio", "producto", "proveedor", "cliente", "procedimiento",
    "preferencia", "definicion", "operacion", "conocimiento_empresa", "instruccion",
}
SENSITIVE = re.compile(r"\b(password|contraseñ[aa]|api[_ -]?key|token|secreto|private key|clave privada|cvv|nip)\b", re.I)
EXPLICIT_REMEMBER = re.compile(r"\b(recuerda|recordar|memoriza|memorizar|guarda(?: esto)?|guardar como memoria)\b", re.I)
STABLE_RULE = re.compile(r"\b(para nosotros|en la empresa|nuestra regla|regla de negocio|siempre se calcula|se define como|procedimiento)\b", re.I)


@dataclass
class MemoryDecision:
    action: str
    category: str = "conocimiento_empresa"
    content: str = ""
    reason: str = ""
    sensitivity: str = "normal"
    confidence: float = 0.7
    importance: float = 0.6


class MemoryManager:
    def __init__(self, db: Database, embeddings: EmbeddingProvider, vectors: VectorStore):
        self.db = db
        self.embeddings = embeddings
        self.vectors = vectors

    def decide(self, text: str) -> MemoryDecision:
        text = (text or "").strip()
        if not text:
            return MemoryDecision("skip", reason="vacio")
        stable_rule_match = bool(STABLE_RULE.search(text))
        category = "regla_negocio" if (stable_rule_match or "regla" in text.lower() or ("utilidad" in text.lower() and "=" in text)) else "conocimiento_empresa"
        if SENSITIVE.search(text):
            if EXPLICIT_REMEMBER.search(text):
                return MemoryDecision("pending", category, self._clean_explicit(text), "informacion sensible requiere confirmacion", "sensitive", 0.55, 0.8)
            return MemoryDecision("skip", category, reason="informacion sensible no se guarda automaticamente", sensitivity="sensitive")
        if EXPLICIT_REMEMBER.search(text):
            return MemoryDecision("save", category, self._clean_explicit(text), "solicitud explicita", "normal", 0.9, 0.8)
        if stable_rule_match:
            return MemoryDecision("pending", category, text, "posible conocimiento estable; requiere confirmacion", "normal", 0.7, 0.8)
        return MemoryDecision("skip", reason="contexto conversacional")

    @staticmethod
    def _clean_explicit(text: str) -> str:
        return re.sub(r"^\s*(recuerda|memoriza|guarda(?: esto)?(?: como memoria)?)[,:\s-]*", "", text, flags=re.I).strip() or text.strip()

    @staticmethod
    def _row(row) -> Dict[str, Any]:
        data = dict(row)
        data["tags"] = json.loads(data.pop("tags_json") or "[]")
        data["active"] = bool(data["active"])
        return data

    def _snapshot(self, memory_id: str, changed_by: str, reason: str) -> None:
        row = self.db.one("SELECT * FROM memories WHERE id=?", (memory_id,))
        if row:
            self.db.execute(
                "INSERT INTO memory_history(memory_id,version,snapshot_json,changed_by,changed_at,reason) VALUES(?,?,?,?,?,?)",
                (memory_id, int(row["version"]), json.dumps(dict(row), ensure_ascii=False), changed_by, utcnow(), reason),
            )

    def create(
        self,
        principal: Principal,
        content: str,
        category: str = "conocimiento_empresa",
        *,
        scope: str = "company",
        source_type: str = "user",
        source_ref: Optional[str] = None,
        confidence: float = 0.8,
        importance: float = 0.6,
        tags: Optional[Sequence[str]] = None,
        expires_at: Optional[str] = None,
        sensitivity: str = "normal",
        status: str = "active",
        supersedes_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        if category not in CATEGORIES:
            category = "conocimiento_empresa"
        if scope not in {"company", "user"}:
            raise ValueError("scope invalido")
        memory_id = str(uuid.uuid4())
        now = utcnow()
        owner = principal.user_id if scope == "user" else None
        active = 1 if status == "active" else 0
        self.db.execute(
            "INSERT INTO memories(id,company_id,user_id,scope,category,content,source_type,source_ref,confidence,importance,tags_json,sensitivity,status,active,expires_at,version,supersedes_id,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                memory_id, principal.company_id, owner, scope, category, content.strip(), source_type,
                source_ref, float(confidence), float(importance), json.dumps(list(tags or []), ensure_ascii=False),
                sensitivity, status, active, expires_at, 1, supersedes_id, now, now,
            ),
        )
        self._snapshot(memory_id, principal.user_id, "create")
        if active:
            vector = self.embeddings.embed([content])[0]
            self.vectors.upsert(
                "memory", memory_id, vector,
                {"memory_id": memory_id, "company_id": principal.company_id, "user_id": owner, "scope": scope, "category": category},
            )
        self.db.audit("memory.create", principal.company_id, principal.user_id, "memory", memory_id, details={"category": category, "scope": scope, "status": status})
        return self.get(principal, memory_id, include_pending=True)

    def get(self, principal: Principal, memory_id: str, include_pending: bool = False) -> Dict[str, Any]:
        clause, args = scope_clause(principal)
        row = self.db.one(f"SELECT * FROM memories WHERE id=? AND {clause}", (memory_id, *args))
        if not row or (not include_pending and (not row["active"] or row["status"] != "active")):
            raise KeyError("Memoria no encontrada")
        return self._row(row)

    def list(self, principal: Principal, *, include_inactive: bool = False, status: Optional[str] = None, limit: int = 200) -> List[Dict[str, Any]]:
        clause, args = scope_clause(principal)
        sql = f"SELECT * FROM memories WHERE {clause}"
        params = list(args)
        if not include_inactive:
            sql += " AND active=1"
        if status:
            sql += " AND status=?"
            params.append(status)
        sql += " ORDER BY importance DESC, updated_at DESC LIMIT ?"
        params.append(limit)
        return [self._row(row) for row in self.db.query(sql, params)]

    @staticmethod
    def _lex_tokens(value: str) -> set[str]:
        normalized = unicodedata.normalize("NFKD", (value or "").lower())
        normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
        tokens = set(re.findall(r"[a-z0-9_]+", normalized))
        stop = {
            "como", "cual", "cuales", "que", "quien", "donde", "cuando", "para", "por", "con",
            "una", "uno", "unos", "unas", "del", "las", "los", "de", "la", "el", "se", "es",
            "nuestro", "nuestra", "nuestros", "nuestras", "empresa", "regla", "operacion"
        }
        return {t for t in tokens if len(t) > 2 and t not in stop}

    def search_lexical(self, principal: Principal, query: str, limit: int = 6, min_score: float = 0.18) -> List[Dict[str, Any]]:
        """Recuperación local rápida sin embeddings.

        Se usa como fast-path para reglas/definiciones directas. No sustituye la
        búsqueda semántica RAG; evita arrancar el modelo de embeddings para una
        pregunta que puede resolverse de forma inequívoca desde SQLite.
        """
        qtokens = self._lex_tokens(query)
        if not qtokens:
            return []
        output: List[Dict[str, Any]] = []
        for memory in self.list(principal, include_inactive=False, limit=500):
            if memory.get("status") != "active":
                continue
            mtokens = self._lex_tokens(memory.get("content", ""))
            overlap = len(qtokens & mtokens)
            if not overlap:
                continue
            # Cobertura de la pregunta + pequeña ponderación por importancia.
            coverage = overlap / max(1, len(qtokens))
            precision = overlap / max(1, min(len(mtokens), 12))
            score = coverage * 0.72 + precision * 0.18 + float(memory.get("importance", 0.6)) * 0.10
            if score >= min_score:
                item = dict(memory)
                item["score"] = round(score, 4)
                item["retrieval"] = "lexical-fast-path"
                output.append(item)
        output.sort(key=lambda x: (x["score"], x.get("importance", 0.0)), reverse=True)
        return output[:limit]

    def search(self, principal: Principal, query: str, limit: int = 6, min_score: float = 0.20) -> List[Dict[str, Any]]:
        if not query.strip():
            return []
        clause, args = scope_clause(principal)
        exists = self.db.one(f"SELECT 1 FROM memories WHERE active=1 AND status='active' AND {clause} LIMIT 1", args)
        if not exists:
            return []
        qvector = self.embeddings.embed([query])[0]
        candidates = self.vectors.search("memory", qvector, principal, max(limit * 4, 20))
        qtokens = set(re.findall(r"\w+", query.lower()))
        now = datetime.now(timezone.utc)
        output = []
        for candidate in candidates:
            memory_id = candidate["payload"].get("memory_id") or candidate["vector_id"]
            try:
                memory = self.get(principal, memory_id)
            except Exception:
                continue
            if memory.get("expires_at"):
                try:
                    if datetime.fromisoformat(memory["expires_at"]) < now:
                        continue
                except Exception:
                    pass
            mtokens = set(re.findall(r"\w+", memory["content"].lower()))
            keyword = len(qtokens & mtokens) / max(1, len(qtokens))
            score = float(candidate["score"]) * 0.72 + keyword * 0.18 + float(memory["importance"]) * 0.10
            if score >= min_score:
                memory["score"] = round(score, 4)
                output.append(memory)
        output.sort(key=lambda x: x["score"], reverse=True)
        return output[:limit]

    def update(self, principal: Principal, memory_id: str, **changes) -> Dict[str, Any]:
        current = self.get(principal, memory_id, include_pending=True)
        self._snapshot(memory_id, principal.user_id, "update")
        allowed = {"content", "category", "confidence", "importance", "tags", "expires_at", "active", "status", "sensitivity", "source_ref"}
        sets, values = [], []
        for key, value in changes.items():
            if key not in allowed:
                continue
            db_key = "tags_json" if key == "tags" else key
            if key == "tags":
                value = json.dumps(list(value or []), ensure_ascii=False)
            if key == "active":
                value = 1 if value else 0
            sets.append(f"{db_key}=?")
            values.append(value)
        if not sets:
            return current
        sets.extend(["version=version+1", "updated_at=?"])
        values.extend([utcnow(), memory_id])
        self.db.execute("UPDATE memories SET " + ",".join(sets) + " WHERE id=?", values)
        updated = self.get(principal, memory_id, include_pending=True)
        if updated["active"] and updated["status"] == "active":
            vector = self.embeddings.embed([updated["content"]])[0]
            self.vectors.upsert(
                "memory", memory_id, vector,
                {"memory_id": memory_id, "company_id": updated["company_id"], "user_id": updated["user_id"], "scope": updated["scope"], "category": updated["category"]},
            )
        else:
            self.vectors.delete("memory", [memory_id])
        self.db.audit("memory.update", principal.company_id, principal.user_id, "memory", memory_id, details={"fields": list(changes)})
        return updated

    def confirm(self, principal: Principal, memory_id: str) -> Dict[str, Any]:
        current = self.get(principal, memory_id, include_pending=True)
        supersedes = current.get("supersedes_id")
        if supersedes:
            try:
                self.get(principal, supersedes, include_pending=True)
                self._snapshot(supersedes, principal.user_id, "superseded")
                self.db.execute("UPDATE memories SET active=0,status='superseded',version=version+1,updated_at=? WHERE id=?", (utcnow(), supersedes))
                self.vectors.delete("memory", [supersedes])
                self.db.audit("memory.supersede", principal.company_id, principal.user_id, "memory", supersedes, details={"replacement": memory_id})
            except Exception:
                pass
        return self.update(principal, memory_id, status="active", active=True, confidence=max(0.8, float(current["confidence"])))

    def forget(self, principal: Principal, memory_id: str) -> None:
        self.get(principal, memory_id, include_pending=True)
        self._snapshot(memory_id, principal.user_id, "forget")
        self.db.execute("UPDATE memories SET active=0,status='forgotten',version=version+1,updated_at=? WHERE id=?", (utcnow(), memory_id))
        self.vectors.delete("memory", [memory_id])
        self.db.audit("memory.forget", principal.company_id, principal.user_id, "memory", memory_id)

    def propose_from_message(self, principal: Principal, text: str) -> Optional[Dict[str, Any]]:
        decision = self.decide(text)
        if decision.action == "skip":
            return None
        supersedes_id = None
        try:
            # Detectar duplicados/conflictos no depende únicamente de similitud vectorial.
            # Reglas empresariales que solo cambian un valor (p. ej. 30 -> 45 días)
            # deben proponerse como actualización y nunca coexistir silenciosamente.
            normalized_new = re.sub(r"\W+", "", decision.content.lower())
            semantic = [m for m in self.search(principal, decision.content, limit=8, min_score=0.08) if m.get("category") == decision.category]
            active_same_category = [m for m in self.list(principal, include_inactive=False, limit=500) if m.get("category") == decision.category]
            by_id = {m["id"]: m for m in (*semantic, *active_same_category)}
            existing = list(by_id.values())

            def signature(value: str) -> set[str]:
                # Los números suelen ser precisamente el dato que cambia en una regla.
                # Los excluimos para comparar el concepto estable de la oración.
                return {
                    token for token in re.findall(r"[a-záéíóúñü]+", (value or "").lower())
                    if len(token) > 2 and token not in {"para", "nosotros", "empresa", "nuestra", "regla"}
                }

            new_sig = signature(decision.content)
            best_conflict = None
            best_score = -1.0
            for memory in existing:
                normalized_old = re.sub(r"\W+", "", memory["content"].lower())
                if normalized_old == normalized_new:
                    return None
                old_sig = signature(memory["content"])
                lexical = len(new_sig & old_sig) / max(1, len(new_sig | old_sig))
                semantic_score = float(memory.get("score", 0.0))
                combined = max(lexical, semantic_score)
                if combined > best_score:
                    best_conflict, best_score = memory, combined

            # 0.50 lexical cubre cambios de valores en una misma regla; 0.35 conserva
            # compatibilidad con el recuperador semántico cuando el embedding es bueno.
            if best_conflict and best_score >= 0.35:
                supersedes_id = best_conflict["id"]
        except Exception:
            pass
        status = "pending" if decision.action == "pending" or supersedes_id else "active"
        return self.create(
            principal,
            decision.content,
            decision.category,
            scope="company",
            source_type="conversation",
            confidence=decision.confidence,
            importance=decision.importance,
            sensitivity=decision.sensitivity,
            status=status,
            supersedes_id=supersedes_id,
        )
