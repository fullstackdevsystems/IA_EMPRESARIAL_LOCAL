from __future__ import annotations

import ast
import contextlib
import contextvars
import json
import re
import unicodedata
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Iterator, List, Optional, Sequence

import pandas as pd

from .database import Database, utcnow
from .knowledge_governance import KnowledgeGovernance
from .precedence_engine import PrecedenceEngine
from .security import Principal, scope_clause
from .semantic_registry import bridge_roles

BINDING_SCHEMA = r"""
CREATE TABLE IF NOT EXISTS analytic_rule_bindings (
    id TEXT PRIMARY KEY,
    rule_id TEXT NOT NULL,
    company_id TEXT NOT NULL,
    user_id TEXT,
    scope TEXT NOT NULL DEFAULT 'company',
    rule_type TEXT NOT NULL,
    target TEXT NOT NULL,
    priority INTEGER NOT NULL DEFAULT 100,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(rule_id, rule_type, target),
    FOREIGN KEY(rule_id) REFERENCES business_rules(id)
);
CREATE INDEX IF NOT EXISTS idx_analytic_binding_scope
ON analytic_rule_bindings(company_id,user_id,scope,active,rule_type,target,priority);
"""

VALID_RULE_TYPES = {"metric", "row_filter"}
_CURRENT_ANALYTIC_CONTEXT: contextvars.ContextVar[Optional[Dict[str, Any]]] = contextvars.ContextVar(
    "ia_enterprise_analytic_context", default=None
)

ROLE_ALIASES = {
    "sales": {"sales", "revenue", "venta", "ventas", "importe", "venta_neta", "venta_bruta"},
    "cost": {"cost", "total_cost", "costo", "costo_total"},
    "freight": {"freight", "flete", "costo_flete"},
    "quantity": {"quantity", "cantidad", "unidades", "volumen", "toneladas"},
    "price": {"price", "unit_price", "precio", "precio_venta"},
    "profit": {"profit", "utilidad", "ganancia"},
    "customer": {"customer", "cliente"},
    "product": {"product", "producto", "articulo"},
    "seller": {"seller", "vendedor", "ejecutivo"},
    "zone": {"zone", "zona", "region"},
    "supplier": {"supplier", "proveedor", "vendor"},
    "date": {"date", "fecha"},
    "invoice": {"invoice", "factura", "referencia", "refer", "folio"},
}


def _norm(value: Any) -> str:
    s = str(value or "").strip().lower()
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9_]+", "_", s).strip("_")


def _canonical_role(name: str) -> Optional[str]:
    n = _norm(name)
    for role, aliases in ROLE_ALIASES.items():
        if n in {_norm(x) for x in aliases}:
            return role
    return None


def _jsonable(v: Any) -> Any:
    if isinstance(v, pd.Timestamp):
        return None if pd.isna(v) else v.isoformat()
    if hasattr(v, "item"):
        try:
            return v.item()
        except Exception:
            pass
    return v


class SafeRuleEvaluator:
    """Evaluador determinístico de expresiones empresariales.

    Soporta aritmética, comparaciones y operadores booleanos. No permite llamadas,
    atributos, índices, imports, comprehensions ni ejecución de código arbitrario.
    """

    def __init__(self, frame: pd.DataFrame, roles: Dict[str, Any]):
        self.frame = frame
        self.roles = bridge_roles(roles)
        self._physical = {_norm(c): str(c) for c in frame.columns}

    def _column(self, name: str) -> pd.Series:
        n = _norm(name)
        role = _canonical_role(n)
        column = None
        if role:
            if role == "sales":
                column = self.roles.get("revenue") or self.roles.get("sales")
            elif role == "cost":
                column = self.roles.get("total_cost") or self.roles.get("cost")
            elif role == "price":
                column = self.roles.get("unit_price") or self.roles.get("price")
            else:
                column = self.roles.get(role)
        if not column:
            column = self._physical.get(n)
        if not column or column not in self.frame.columns:
            raise ValueError(f"La regla requiere '{name}', pero no existe una columna/rol validado para ese concepto")
        return self.frame[column]

    @staticmethod
    def _numeric(value: Any) -> Any:
        if isinstance(value, pd.Series):
            return pd.to_numeric(value, errors="coerce")
        return value

    @staticmethod
    def _bool(value: Any, index) -> pd.Series:
        if isinstance(value, pd.Series):
            if value.dtype == bool:
                return value.fillna(False)
            return value.fillna(False).astype(bool)
        return pd.Series([bool(value)] * len(index), index=index, dtype=bool)

    def evaluate(self, expression: str) -> Any:
        tree = ast.parse(str(expression or "").strip(), mode="eval")

        def ev(node):
            if isinstance(node, ast.Expression):
                return ev(node.body)
            if isinstance(node, ast.Name):
                return self._column(node.id)
            if isinstance(node, ast.Constant) and isinstance(node.value, (int, float, str, bool, type(None))):
                return node.value
            if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub, ast.Not)):
                value = ev(node.operand)
                if isinstance(node.op, ast.Not):
                    return ~self._bool(value, self.frame.index)
                value = self._numeric(value)
                return value if isinstance(node.op, ast.UAdd) else -value
            if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
                left, right = self._numeric(ev(node.left)), self._numeric(ev(node.right))
                if isinstance(node.op, ast.Add): return left + right
                if isinstance(node.op, ast.Sub): return left - right
                if isinstance(node.op, ast.Mult): return left * right
                if isinstance(node.op, ast.Div):
                    if isinstance(right, pd.Series):
                        return left / right.replace(0, pd.NA)
                    if right == 0: raise ValueError("Division entre cero en regla empresarial")
                    return left / right
            if isinstance(node, ast.BoolOp) and isinstance(node.op, (ast.And, ast.Or)):
                vals = [self._bool(ev(v), self.frame.index) for v in node.values]
                out = vals[0]
                for value in vals[1:]:
                    out = out & value if isinstance(node.op, ast.And) else out | value
                return out
            if isinstance(node, ast.Compare):
                left = ev(node.left)
                result = pd.Series([True] * len(self.frame), index=self.frame.index, dtype=bool)
                for op, comp in zip(node.ops, node.comparators):
                    right = ev(comp)
                    if isinstance(op, ast.Eq): cur = left == right
                    elif isinstance(op, ast.NotEq): cur = left != right
                    elif isinstance(op, ast.Gt): cur = self._numeric(left) > self._numeric(right)
                    elif isinstance(op, ast.GtE): cur = self._numeric(left) >= self._numeric(right)
                    elif isinstance(op, ast.Lt): cur = self._numeric(left) < self._numeric(right)
                    elif isinstance(op, ast.LtE): cur = self._numeric(left) <= self._numeric(right)
                    else: raise ValueError(f"Comparador no permitido: {type(op).__name__}")
                    result = result & self._bool(cur, self.frame.index)
                    left = right
                return result
            raise ValueError(f"Operacion no permitida en regla empresarial: {type(node).__name__}")

        return ev(tree)




def evaluate_analytic_context(frame: pd.DataFrame, roles: Dict[str, Any], analytic_context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Ejecuta un contexto ya autorizado, sin acceso a DB ni identidad global.

    Esto permite que BI, dashboards y StructuredData compartan exactamente la misma
    semántica de reglas. El contexto solo debe provenir de AnalyticRuleEngine.build_context.
    """
    ctx = analytic_context or {}
    bindings = list(ctx.get("bindings") or [])
    work = frame.copy()
    mask = pd.Series([True] * len(work), index=work.index, dtype=bool)
    applied_filters: List[Dict[str, Any]] = []
    applied_metrics: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []

    for item in [x for x in bindings if x.get("rule_type") == "row_filter"]:
        rule = item.get("rule") or {}
        try:
            value = SafeRuleEvaluator(work, roles).evaluate(rule.get("expression", ""))
            rmask = SafeRuleEvaluator._bool(value, work.index)
            mask &= rmask
            applied_filters.append({
                "rule_id": rule.get("id"), "name": rule.get("name"), "version": rule.get("version"),
                "target": item.get("target"), "expression": rule.get("expression"),
                "rows_before": int(len(work)), "rows_after": int(mask.sum()),
                "source_type": rule.get("source_type"), "source_ref": rule.get("source_ref"),
            })
        except Exception as exc:
            errors.append({"rule_id": rule.get("id"), "name": rule.get("name"), "stage": "row_filter", "target": item.get("target"), "error": str(exc)})

    filtered = work.loc[mask].copy()
    metrics: Dict[str, pd.Series] = {}
    for item in [x for x in bindings if x.get("rule_type") == "metric"]:
        rule = item.get("rule") or {}
        target = _norm(item.get("target"))
        try:
            value = SafeRuleEvaluator(filtered, roles).evaluate(rule.get("expression", ""))
            if isinstance(value, pd.Series):
                metrics[target] = pd.to_numeric(value, errors="coerce")
            elif isinstance(value, (int, float)):
                metrics[target] = pd.Series([float(value)] * len(filtered), index=filtered.index, dtype="float64")
            else:
                raise ValueError("Una regla metric debe producir un valor numerico")
            applied_metrics.append({
                "rule_id": rule.get("id"), "name": rule.get("name"), "version": rule.get("version"),
                "target": target, "expression": rule.get("expression"),
                "source_type": rule.get("source_type"), "source_ref": rule.get("source_ref"),
            })
        except Exception as exc:
            errors.append({"rule_id": rule.get("id"), "name": rule.get("name"), "stage": "metric", "target": target, "error": str(exc)})

    return {
        "frame": filtered, "row_mask": mask, "metrics": metrics,
        "applied_filters": applied_filters, "applied_metrics": applied_metrics, "errors": errors,
        "rows_input": int(len(frame)), "rows_output": int(len(filtered)),
    }

class AnalyticRuleEngine:
    def __init__(self, db: Database, governance: KnowledgeGovernance, precedence: PrecedenceEngine):
        self.db = db
        self.governance = governance
        self.precedence = precedence
        self.ensure_schema()

    def ensure_schema(self) -> None:
        with self.db.tx() as con:
            con.executescript(BINDING_SCHEMA)

    def bind_rule(
        self,
        principal: Principal,
        rule_id: str,
        *,
        rule_type: str,
        target: str,
        priority: int = 100,
        scope: str = "company",
    ) -> Dict[str, Any]:
        rule_type = str(rule_type).strip().lower()
        if rule_type not in VALID_RULE_TYPES:
            raise ValueError("rule_type debe ser metric o row_filter")
        if not str(target).strip():
            raise ValueError("target es obligatorio")
        # Solo reglas existentes y accesibles pueden vincularse.
        self.governance.get_rule(principal, rule_id, include_nonvalidated=True)
        owner = principal.user_id if scope == "user" else None
        if scope not in {"company", "user"}:
            raise ValueError("scope invalido")
        existing = self.db.one(
            "SELECT * FROM analytic_rule_bindings WHERE rule_id=? AND rule_type=? AND target=?",
            (rule_id, rule_type, str(target).strip()),
        )
        now = utcnow()
        if existing:
            self.db.execute(
                "UPDATE analytic_rule_bindings SET company_id=?,user_id=?,scope=?,priority=?,active=1,updated_at=? WHERE id=?",
                (principal.company_id, owner, scope, int(priority), now, existing["id"]),
            )
            binding_id = existing["id"]
        else:
            binding_id = str(uuid.uuid4())
            self.db.execute(
                "INSERT INTO analytic_rule_bindings(id,rule_id,company_id,user_id,scope,rule_type,target,priority,active,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (binding_id, rule_id, principal.company_id, owner, scope, rule_type, str(target).strip(), int(priority), 1, now, now),
            )
        self.db.audit("knowledge.rule.bind", principal.company_id, principal.user_id, "business_rule", rule_id,
                      details={"rule_type": rule_type, "target": str(target).strip(), "priority": int(priority)})
        return dict(self.db.one("SELECT * FROM analytic_rule_bindings WHERE id=?", (binding_id,)))

    def _bindings(self, principal: Principal, *, rule_type: Optional[str] = None, target: Optional[str] = None) -> List[Dict[str, Any]]:
        clause, args = scope_clause(principal, "b")
        sql = f"SELECT b.* FROM analytic_rule_bindings b WHERE b.active=1 AND {clause}"
        params = list(args)
        if rule_type:
            sql += " AND b.rule_type=?"; params.append(rule_type)
        if target:
            sql += " AND b.target=?"; params.append(target)
        sql += " ORDER BY b.priority DESC,b.updated_at DESC"
        return [dict(r) for r in self.db.query(sql, params)]

    def applicable_bindings(self, principal: Principal, *, on_date: Optional[str] = None) -> List[Dict[str, Any]]:
        valid = {r["id"]: r for r in self.governance.applicable_rules(principal, on_date=on_date)}
        out = []
        for binding in self._bindings(principal):
            rule = valid.get(binding["rule_id"])
            if not rule:
                continue
            item = dict(binding)
            item["rule"] = rule
            out.append(item)
        return out

    def build_context(self, principal: Principal, roles: Dict[str, Any], *, on_date: Optional[str] = None) -> Dict[str, Any]:
        bindings = self.applicable_bindings(principal, on_date=on_date)
        return {
            "version": "r10.6",
            "company_id": principal.company_id,
            "user_id": principal.user_id,
            "roles": bridge_roles(roles),
            "bindings": bindings,
            "precedence": "validated_business_rule > validated_semantic_definition > system_inference",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def apply(self, frame: pd.DataFrame, roles: Dict[str, Any], analytic_context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        result = evaluate_analytic_context(frame, roles, analytic_context)
        filtered = result["frame"].copy()
        target_columns = {
            "profit": "_utilidad", "sales": "_ventas", "cost": "_costo",
            "freight": "_flete", "quantity": "_cantidad", "commission": "_comision",
        }
        for target, values in result["metrics"].items():
            out_col = target_columns.get(target, "_metric_" + re.sub(r"[^a-z0-9_]+", "_", target)[:40])
            filtered[out_col] = values.reindex(filtered.index)
        result["frame"] = filtered
        return result

    @contextlib.contextmanager
    def bind(self, principal: Principal, roles: Dict[str, Any], *, on_date: Optional[str] = None) -> Iterator[Dict[str, Any]]:
        ctx = self.build_context(principal, roles, on_date=on_date)
        token = _CURRENT_ANALYTIC_CONTEXT.set(ctx)
        try:
            yield ctx
        finally:
            _CURRENT_ANALYTIC_CONTEXT.reset(token)


def current_analytic_context() -> Optional[Dict[str, Any]]:
    value = _CURRENT_ANALYTIC_CONTEXT.get()
    return dict(value) if isinstance(value, dict) else None
