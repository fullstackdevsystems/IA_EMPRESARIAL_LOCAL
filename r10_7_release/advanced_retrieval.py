from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from .documents import DocumentService
from .memory import MemoryManager
from .security import Principal

AREA_TERMS: Dict[str, Tuple[str, ...]] = {
    "ventas": ("venta", "ventas", "cliente", "clientes", "vendedor", "vendedores", "factura", "facturacion", "ingreso", "margen", "utilidad"),
    "compras": ("compra", "compras", "proveedor", "proveedores", "orden de compra", "abastecimiento"),
    "inventarios": ("inventario", "existencia", "stock", "almacen", "almacén", "sku", "lote"),
    "finanzas": ("finanza", "finanzas", "flujo", "cartera", "cuenta por cobrar", "cuentas por cobrar", "presupuesto", "tesoreria", "tesorería"),
    "logistica": ("logistica", "logística", "flete", "fletes", "transporte", "ruta", "origen", "destino"),
    "recursos_humanos": ("recursos humanos", "rrhh", "empleado", "empleados", "nomina", "nómina", "vacaciones", "asistencia"),
    "contabilidad": ("contabilidad", "contable", "poliza", "póliza", "cfdi", "impuesto", "fiscal"),
    "direccion": ("direccion", "dirección", "directivo", "direccion general", "consejo", "ejecutivo"),
}

STOP = {
    "como","cual","cuales","que","para","por","con","una","uno","unos","unas","del","las","los","de","la","el","se","es",
    "en","al","y","o","mi","mis","nuestro","nuestra","empresa","datos","informacion","información","dime","muestra","analiza","analisis","análisis",
}


def _norm(v: Any) -> str:
    text = str(v or "").strip().lower()
    text = "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9_]+", " ", text).strip()


def _tokens(v: Any) -> set[str]:
    return {t for t in _norm(v).split() if len(t) > 2 and t not in STOP}


def detect_areas(question: str, limit: int = 3) -> List[str]:
    q = _norm(question)
    scored: List[Tuple[int, str]] = []
    for area, terms in AREA_TERMS.items():
        score = 0
        for term in terms:
            nt = _norm(term)
            if nt and nt in q:
                score += max(1, len(nt.split()))
        if score:
            scored.append((score, area))
    scored.sort(key=lambda x: (-x[0], x[1]))
    return [a for _, a in scored[:limit]]


def _parse_meta(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str) and value.strip():
        try:
            obj = json.loads(value)
            return obj if isinstance(obj, dict) else {}
        except Exception:
            return {}
    return {}


def _valid_on(meta: Dict[str, Any], now: datetime) -> bool:
    def parse(name: str) -> Optional[datetime]:
        raw = meta.get(name)
        if not raw:
            return None
        try:
            dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            return None
    start = parse("valid_from") or parse("vigente_desde")
    end = parse("valid_to") or parse("vigente_hasta") or parse("expires_at")
    if start and now < start:
        return False
    if end and now > end:
        return False
    return True


def _authority(item: Dict[str, Any], kind: str) -> float:
    if kind == "rule":
        return 1.0
    if kind == "document":
        meta = _parse_meta(item.get("metadata_json") or item.get("metadata"))
        if str(meta.get("official", "")).lower() in {"1","true","yes","si","sí"}:
            return 0.95
        return 0.78
    if kind == "memory":
        status = str(item.get("status") or "").upper()
        if status in {"VALIDADO","VALIDATED"}:
            return 0.90
        return 0.62
    return 0.50


def _lexical(query_tokens: set[str], text: str) -> float:
    if not query_tokens:
        return 0.0
    tt = _tokens(text)
    if not tt:
        return 0.0
    overlap = len(query_tokens & tt)
    return (overlap / max(1, len(query_tokens))) * 0.72 + (overlap / max(1, min(len(tt), 24))) * 0.28


def _area_score(areas: Sequence[str], item: Dict[str, Any], text: str) -> float:
    if not areas:
        return 0.5
    meta = _parse_meta(item.get("metadata_json") or item.get("metadata"))
    explicit = _norm(item.get("area") or meta.get("area") or "")
    if explicit:
        return 1.0 if any(_norm(a) == explicit for a in areas) else 0.10
    text_n = _norm(text)
    hits = 0
    for area in areas:
        for term in AREA_TERMS.get(area, ()):
            if _norm(term) in text_n:
                hits += 1
                break
    return 0.8 if hits else 0.45


def _fingerprint(text: str) -> str:
    compact = " ".join(_norm(text).split())
    return hashlib.sha256(compact.encode("utf-8", errors="ignore")).hexdigest()


def _similar(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / max(1, len(ta | tb))


def _compress_text(text: str, question: str, max_chars: int) -> str:
    text = (text or "").strip()
    if len(text) <= max_chars:
        return text
    qtokens = _tokens(question)
    parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+|\n+", text) if p.strip()]
    ranked = []
    for i, part in enumerate(parts):
        score = _lexical(qtokens, part)
        ranked.append((score, -i, part))
    ranked.sort(reverse=True)
    chosen, total = [], 0
    for _, neg_i, part in ranked:
        if total + len(part) + 1 > max_chars:
            continue
        chosen.append((-neg_i, part))
        total += len(part) + 1
        if total >= int(max_chars * 0.85):
            break
    if not chosen:
        return text[:max_chars].rstrip() + "…"
    chosen.sort()
    out = " ".join(p for _, p in chosen)
    return out[:max_chars].rstrip() + ("…" if len(out) > max_chars else "")


@dataclass
class RetrievalBundle:
    memories: List[Dict[str, Any]]
    chunks: List[Dict[str, Any]]
    rules: List[Dict[str, Any]]
    areas: List[str]
    stats: Dict[str, Any]


class AdvancedRetrievalEngine:
    """R10.7: recuperación local selectiva, auditable y CPU-friendly.

    No reemplaza VectorStore ni embeddings. Expande candidatos usando los servicios
    existentes y aplica gobernanza/reranking/deduplicación/compresión antes del LLM.
    """

    def __init__(self, memory: MemoryManager, documents: DocumentService, governance=None, cfg: Optional[Dict[str, Any]] = None):
        self.memory = memory
        self.documents = documents
        self.governance = governance
        self.cfg = dict(cfg or {})

    def _rules(self, principal: Principal, areas: Sequence[str]) -> List[Dict[str, Any]]:
        if not self.governance:
            return []
        rows: List[Dict[str, Any]] = []
        seen = set()
        targets = list(areas) or [None]
        for area in targets:
            try:
                current = self.governance.applicable_rules(principal, area=area)
            except Exception:
                current = []
            for r in current:
                rid = r.get("id")
                if rid in seen:
                    continue
                seen.add(rid)
                rows.append(dict(r))
        return rows

    def retrieve(self, principal: Principal, question: str) -> RetrievalBundle:
        areas = detect_areas(question)
        qtokens = _tokens(question)
        mem_limit = max(1, int(self.cfg.get("max_memories", 6)))
        doc_limit = max(1, int(self.cfg.get("max_document_chunks", 8)))
        candidate_factor = max(2, min(int(self.cfg.get("candidate_factor", 4)), 10))
        now = datetime.now(timezone.utc)

        try:
            memories = self.memory.search(principal, question, mem_limit * candidate_factor, float(self.cfg.get("memory_candidate_min_score", 0.08)))
        except Exception:
            memories = []
        try:
            chunks = self.documents.search(principal, question, doc_limit * candidate_factor, float(self.cfg.get("document_candidate_min_score", 0.08)))
        except Exception:
            chunks = []
        rules = self._rules(principal, areas)

        def rerank(items: Iterable[Dict[str, Any]], kind: str, text_key: str) -> List[Dict[str, Any]]:
            ranked = []
            for raw in items:
                item = dict(raw)
                text = str(item.get(text_key) or "")
                meta = _parse_meta(item.get("metadata_json") or item.get("metadata"))
                if not _valid_on(meta, now):
                    continue
                base = float(item.get("score") or 0.0)
                lex = _lexical(qtokens, text)
                area = _area_score(areas, item, text)
                auth = _authority(item, kind)
                score = base * 0.48 + lex * 0.26 + area * 0.12 + auth * 0.14
                item["retrieval_score"] = round(score, 5)
                item["retrieval_area_score"] = round(area, 4)
                item["retrieval_authority"] = round(auth, 4)
                ranked.append(item)
            ranked.sort(key=lambda x: x.get("retrieval_score", 0), reverse=True)
            return ranked

        memories = rerank(memories, "memory", "content")
        chunks = rerank(chunks, "document", "content")
        rules = rerank(rules, "rule", "expression")

        def dedupe(items: List[Dict[str, Any]], text_key: str, limit: int) -> Tuple[List[Dict[str, Any]], int]:
            out: List[Dict[str, Any]] = []
            fingerprints = set()
            removed = 0
            for item in items:
                text = str(item.get(text_key) or "")
                fp = _fingerprint(text)
                if fp in fingerprints or any(_similar(text, str(x.get(text_key) or "")) >= 0.90 for x in out):
                    removed += 1
                    continue
                fingerprints.add(fp)
                out.append(item)
                if len(out) >= limit:
                    break
            return out, removed

        memories, mem_dup = dedupe(memories, "content", mem_limit)
        chunks, doc_dup = dedupe(chunks, "content", doc_limit)
        rules, rule_dup = dedupe(rules, "expression", max(1, int(self.cfg.get("max_rules", 6))))

        per_chunk = max(400, int(self.cfg.get("max_chunk_chars", 1800)))
        for item in chunks:
            item["content_original_chars"] = len(str(item.get("content") or ""))
            item["content"] = _compress_text(str(item.get("content") or ""), question, per_chunk)
            item["content_compressed_chars"] = len(item["content"])

        stats = {
            "areas": areas,
            "memories_selected": len(memories),
            "chunks_selected": len(chunks),
            "rules_selected": len(rules),
            "duplicates_removed": {"memory": mem_dup, "document": doc_dup, "rule": rule_dup},
            "candidate_factor": candidate_factor,
            "reranker": "hybrid-local-r10.7",
            "compression": "query-aware-sentence-selection",
        }
        return RetrievalBundle(memories, chunks, rules, areas, stats)
