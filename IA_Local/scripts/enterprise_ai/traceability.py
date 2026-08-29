from __future__ import annotations

import contextlib
import contextvars
import hashlib
import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Iterator, List, Optional

from .database import Database, utcnow
from .security import Principal, scope_clause

TRACE_SCHEMA = r"""
CREATE TABLE IF NOT EXISTS result_traces (
    id TEXT PRIMARY KEY,
    company_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    trace_type TEXT NOT NULL,
    target_ref TEXT,
    prompt_hash TEXT,
    prompt_preview TEXT,
    status TEXT NOT NULL DEFAULT 'running',
    summary_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    completed_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_result_traces_scope
ON result_traces(company_id,user_id,created_at);
CREATE TABLE IF NOT EXISTS result_trace_steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trace_id TEXT NOT NULL,
    ordinal INTEGER NOT NULL,
    stage TEXT NOT NULL,
    engine TEXT,
    source_type TEXT,
    source_ref TEXT,
    details_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    FOREIGN KEY(trace_id) REFERENCES result_traces(id)
);
CREATE INDEX IF NOT EXISTS idx_trace_steps_trace ON result_trace_steps(trace_id,ordinal);
"""

_SECRET_RE = re.compile(r"(password|contrase(?:n|ñ)a|token|api[_ -]?key|secret|private[_ -]?key|cvv|nip)", re.I)
_CURRENT_MANAGER: contextvars.ContextVar[Optional['TraceabilityManager']] = contextvars.ContextVar('ia_trace_manager', default=None)
_CURRENT_TRACE: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar('ia_trace_id', default=None)


def _safe_scalar(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float)):
        return value
    text = str(value)
    return text[:1000]


def sanitize_details(value: Any, *, depth: int = 0) -> Any:
    """Convierte metadatos a JSON seguro sin copiar secretos ni payloads gigantes."""
    if depth > 5:
        return '[MAX_DEPTH]'
    if isinstance(value, dict):
        out: Dict[str, Any] = {}
        for key, item in value.items():
            k = str(key)[:120]
            if _SECRET_RE.search(k):
                out[k] = '[REDACTED]'
            elif k.lower() in {'content','document_text','prompt','answer','response_text','raw_data','table'}:
                text = str(item or '')
                out[k + '_sha256'] = hashlib.sha256(text.encode('utf-8', errors='ignore')).hexdigest()
                out[k + '_chars'] = len(text)
            else:
                out[k] = sanitize_details(item, depth=depth + 1)
        return out
    if isinstance(value, (list, tuple, set)):
        return [sanitize_details(x, depth=depth + 1) for x in list(value)[:100]]
    return _safe_scalar(value)


class TraceabilityManager:
    def __init__(self, db: Database):
        self.db = db
        self.ensure_schema()

    def ensure_schema(self) -> None:
        with self.db.tx() as con:
            con.executescript(TRACE_SCHEMA)

    def start(self, principal: Principal, *, trace_type: str, target_ref: Optional[str] = None, prompt: Optional[str] = None) -> str:
        trace_id = str(uuid.uuid4())
        prompt_text = str(prompt or '')
        preview = re.sub(r'\s+', ' ', prompt_text).strip()[:220] or None
        prompt_hash = hashlib.sha256(prompt_text.encode('utf-8', errors='ignore')).hexdigest() if prompt_text else None
        self.db.execute(
            "INSERT INTO result_traces(id,company_id,user_id,trace_type,target_ref,prompt_hash,prompt_preview,status,summary_json,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (trace_id, principal.company_id, principal.user_id, str(trace_type), target_ref, prompt_hash, preview, 'running', '{}', utcnow()),
        )
        self.db.audit('trace.start', principal.company_id, principal.user_id, 'result_trace', trace_id, details={'trace_type': trace_type, 'target_ref': target_ref})
        return trace_id

    def add_step(self, trace_id: str, stage: str, *, engine: Optional[str] = None, source_type: Optional[str] = None,
                 source_ref: Optional[str] = None, details: Optional[Dict[str, Any]] = None) -> None:
        row = self.db.one('SELECT COALESCE(MAX(ordinal),0)+1 AS n FROM result_trace_steps WHERE trace_id=?', (trace_id,))
        ordinal = int(row['n'] if row else 1)
        payload = sanitize_details(details or {})
        self.db.execute(
            'INSERT INTO result_trace_steps(trace_id,ordinal,stage,engine,source_type,source_ref,details_json,created_at) VALUES(?,?,?,?,?,?,?,?)',
            (trace_id, ordinal, str(stage), engine, source_type, source_ref, json.dumps(payload, ensure_ascii=False), utcnow()),
        )

    def complete(self, trace_id: str, *, status: str = 'completed', summary: Optional[Dict[str, Any]] = None) -> None:
        self.db.execute('UPDATE result_traces SET status=?,summary_json=?,completed_at=? WHERE id=?',
                        (status, json.dumps(sanitize_details(summary or {}), ensure_ascii=False), utcnow(), trace_id))

    def get(self, principal: Principal, trace_id: str) -> Dict[str, Any]:
        row = self.db.one('SELECT * FROM result_traces WHERE id=? AND company_id=? AND user_id=?', (trace_id, principal.company_id, principal.user_id))
        if not row:
            raise KeyError('Traza no encontrada')
        data = dict(row)
        try: data['summary'] = json.loads(data.pop('summary_json') or '{}')
        except Exception: data['summary'] = {}
        steps=[]
        for step in self.db.query('SELECT * FROM result_trace_steps WHERE trace_id=? ORDER BY ordinal', (trace_id,)):
            item=dict(step)
            try: item['details']=json.loads(item.pop('details_json') or '{}')
            except Exception: item['details']={}
            steps.append(item)
        data['steps']=steps
        return data

    def list(self, principal: Principal, limit: int = 100) -> List[Dict[str, Any]]:
        rows=self.db.query('SELECT * FROM result_traces WHERE company_id=? AND user_id=? ORDER BY created_at DESC LIMIT ?',
                           (principal.company_id, principal.user_id, max(1,min(int(limit),500))))
        return [dict(r) for r in rows]

    def explain(self, principal: Principal, trace_id: str) -> Dict[str, Any]:
        trace=self.get(principal, trace_id)
        lines=['Cómo obtuve este resultado:']
        for step in trace['steps']:
            d=step.get('details') or {}; stage=step.get('stage')
            if stage=='structured_calculation':
                lines.append(f"- Cálculo determinístico: {d.get('calculation','python/pandas')}; archivo={d.get('file','N/D')}; hoja={d.get('sheet','N/D')}; filas={d.get('rows_used','N/D')}.")
            elif stage=='analytic_rules':
                lines.append(f"- Reglas empresariales: filtros={d.get('filters_count',0)}, métricas={d.get('metrics_count',0)}, filas {d.get('rows_input','N/D')}→{d.get('rows_output','N/D')}.")
            elif stage=='semantic_resolution':
                lines.append(f"- Semántica: {d.get('validated_count',0)} definiciones validadas y {d.get('inferred_count',0)} inferidas.")
            elif stage=='retrieval':
                lines.append(f"- Evidencia recuperada: documentos={d.get('documents',0)}, memorias={d.get('memories',0)}, reglas={d.get('rules',0)}.")
            elif stage=='llm_interpretation':
                lines.append(f"- Interpretación final: {step.get('engine') or 'LLM local'}; las cifras provienen del motor determinístico cuando existe cálculo estructurado.")
            else:
                lines.append(f"- {stage}: {step.get('engine') or 'sistema local'}.")
        return {'trace_id': trace_id, 'status': trace['status'], 'explanation': '\n'.join(lines), 'trace': trace}

    @contextlib.contextmanager
    def scope(self, principal: Principal, *, trace_type: str, target_ref: Optional[str] = None, prompt: Optional[str] = None) -> Iterator[str]:
        trace_id=self.start(principal, trace_type=trace_type, target_ref=target_ref, prompt=prompt)
        mt=_CURRENT_MANAGER.set(self); tt=_CURRENT_TRACE.set(trace_id)
        try:
            yield trace_id
            self.complete(trace_id)
        except Exception as exc:
            self.add_step(trace_id, 'error', engine='runtime', details={'error_type': type(exc).__name__, 'error': str(exc)[:500]})
            self.complete(trace_id, status='error')
            raise
        finally:
            _CURRENT_TRACE.reset(tt); _CURRENT_MANAGER.reset(mt)


def trace_step(stage: str, *, engine: Optional[str] = None, source_type: Optional[str] = None,
               source_ref: Optional[str] = None, details: Optional[Dict[str, Any]] = None) -> None:
    manager=_CURRENT_MANAGER.get(); trace_id=_CURRENT_TRACE.get()
    if manager and trace_id:
        manager.add_step(trace_id, stage, engine=engine, source_type=source_type, source_ref=source_ref, details=details)


def current_trace_id() -> Optional[str]:
    return _CURRENT_TRACE.get()


def build_file_trace(*, filename: str, sheet: Optional[str], rows: int, columns: List[str], roles: Dict[str, Any],
                     derived: Optional[Dict[str, Any]] = None, notes: Optional[List[str]] = None,
                     outputs: Optional[Dict[str, Any]] = None, prompt: Optional[str] = None) -> Dict[str, Any]:
    """Manifiesto no autenticado para reportes generados desde el analizador local."""
    p=str(prompt or '')
    return sanitize_details({
        'trace_version':'r10.9', 'created_at':datetime.now(timezone.utc).isoformat(), 'source':{'file':filename,'sheet':sheet,'rows':rows},
        'columns':list(columns), 'semantic_roles':dict(roles), 'calculations':derived or {}, 'notes':notes or [], 'outputs':outputs or {},
        'prompt_hash':hashlib.sha256(p.encode('utf-8',errors='ignore')).hexdigest() if p else None,
        'calculation_engine':'python/pandas', 'principle':'LLM interpreta; codigo calcula',
    })
