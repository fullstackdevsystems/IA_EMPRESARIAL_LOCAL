from __future__ import annotations

import ast
import re
import unicodedata
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

import pandas as pd

from .knowledge_governance import KnowledgeGovernance
from .security import Principal

PRECEDENCE = [
    "validated_business_rule",
    "validated_semantic_definition",
    "enterprise_configuration",
    "official_document",
    "confirmed_memory",
    "system_inference",
    "llm_general_knowledge",
]

SEMANTIC_ROLE_ALIASES = {
    "date": {"fecha", "fecha_operacion", "fecha_documento", "date"},
    "product": {"producto", "articulo", "item", "sku", "product"},
    "customer": {"cliente", "cliente_nombre", "customer"},
    "customer_id": {"cliente_id", "clave_cliente", "codigo_cliente", "customer_id"},
    "supplier": {"proveedor", "supplier", "vendor"},
    "quantity": {"cantidad", "unidades", "volumen", "toneladas", "quantity"},
    "price": {"precio", "precio_venta", "price"},
    "sales": {"venta", "ventas", "importe", "venta_bruta", "venta_neta", "revenue", "sales"},
    "cost": {"costo", "costo_producto", "cost"},
    "freight": {"flete", "costo_flete", "freight", "shipping"},
    "profit": {"utilidad", "ganancia", "profit"},
    "zone": {"zona", "region", "territorio"},
    "seller": {"vendedor", "ejecutivo", "asesor", "seller"},
    "warehouse": {"almacen", "bodega", "warehouse"},
    "invoice": {"factura", "referencia", "folio", "invoice", "refer"},
}

EXPR_ROLE_ALIASES = {
    "venta": "sales", "ventas": "sales", "importe": "sales", "revenue": "sales", "sales": "sales",
    "costo": "cost", "coste": "cost", "cost": "cost", "costo_producto": "cost",
    "flete": "freight", "freight": "freight", "costo_flete": "freight",
    "cantidad": "quantity", "unidades": "quantity", "toneladas": "quantity", "quantity": "quantity",
    "precio": "price", "price": "price", "precio_venta": "price",
}


def _norm(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9_]+", "_", text).strip("_")


def _role_from_semantic(name: str) -> Optional[str]:
    n = _norm(name)
    for role, aliases in SEMANTIC_ROLE_ALIASES.items():
        if n in {_norm(x) for x in aliases}:
            return role
    return None


class PrecedenceEngine:
    """Aplica conocimiento validado antes de inferencias y del LLM.

    Esta clase no ejecuta texto arbitrario. Las formulas empresariales se evalúan
    con un subconjunto AST estrictamente limitado a operaciones matemáticas.
    """

    def __init__(self, governance: KnowledgeGovernance):
        self.governance = governance

    def semantic_overrides(
        self,
        principal: Principal,
        columns: Sequence[str],
        inferred_roles: Optional[Dict[str, Any]] = None,
        *,
        on_date: Optional[str] = None,
    ) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        roles = dict(inferred_roles or {})
        applied: List[Dict[str, Any]] = []
        physical_lookup = {_norm(c): str(c) for c in columns}
        for physical in columns:
            definition = self.governance.resolve_semantic(principal, str(physical), on_date=on_date)
            if not definition:
                continue
            role = _role_from_semantic(definition.get("semantic_name", ""))
            if not role:
                continue
            # Validated semantic knowledge outranks heuristic inference.
            roles[role] = physical_lookup.get(_norm(physical), str(physical))
            applied.append({
                "definition_id": definition["id"],
                "physical_name": str(physical),
                "semantic_name": definition["semantic_name"],
                "role": role,
                "version": definition.get("version"),
                "source_type": definition.get("source_type"),
                "source_ref": definition.get("source_ref"),
                "precedence": "validated_semantic_definition",
            })
        return roles, applied

    def relevant_rules(
        self,
        principal: Principal,
        question: str = "",
        *,
        area: Optional[str] = None,
        on_date: Optional[str] = None,
        limit: int = 12,
    ) -> List[Dict[str, Any]]:
        rows = self.governance.applicable_rules(principal, area=area, on_date=on_date)
        qtokens = {t for t in _norm(question).split("_") if len(t) > 2}
        scored = []
        for row in rows:
            blob = " ".join(str(row.get(k) or "") for k in ("name", "area", "expression", "description"))
            tokens = {t for t in _norm(blob).split("_") if len(t) > 2}
            overlap = len(qtokens & tokens)
            # If no question is given, return all applicable rules in deterministic order.
            score = overlap * 10 + float(row.get("confidence") or 0) + (1 if not qtokens else 0)
            if not qtokens or overlap or any(x in _norm(question) for x in (_norm(row.get("name")), _norm(row.get("area")))):
                item = dict(row)
                item["precedence"] = "validated_business_rule"
                item["relevance_score"] = round(score, 3)
                scored.append(item)
        scored.sort(key=lambda x: (x["relevance_score"], int(x.get("version") or 1), str(x.get("updated_at") or "")), reverse=True)
        return scored[:limit]

    def rule_for_metric(
        self,
        principal: Principal,
        metric: str,
        *,
        question: str = "",
        area: Optional[str] = None,
        on_date: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        target = _norm(metric)
        aliases = {
            "profit": {"profit", "utilidad", "ganancia", "rentabilidad"},
            "sales": {"sales", "ventas", "venta"},
            "cost": {"cost", "costo", "coste"},
        }.get(target, {target})
        candidates = self.relevant_rules(principal, question or metric, area=area, on_date=on_date, limit=50)
        matches = []
        for rule in candidates:
            name = _norm(rule.get("name"))
            desc = _norm(rule.get("description"))
            if any(a in name or a in desc for a in aliases):
                matches.append(rule)
        if not matches:
            return None
        matches.sort(key=lambda x: (int(x.get("version") or 1), float(x.get("confidence") or 0), str(x.get("updated_at") or "")), reverse=True)
        return matches[0]

    def evaluate_rule(self, frame: pd.DataFrame, roles: Dict[str, Any], rule: Dict[str, Any]) -> pd.Series:
        expression = str(rule.get("expression") or "").strip()
        if not expression:
            raise ValueError("Regla sin expresion")
        tree = ast.parse(expression, mode="eval")

        def series_for_name(name: str) -> pd.Series:
            key = _norm(name)
            role = EXPR_ROLE_ALIASES.get(key)
            column = roles.get(role) if role else None
            if not column:
                # A validated semantic/physical column may be referenced directly.
                for c in frame.columns:
                    if _norm(c) == key:
                        column = c
                        break
            if not column or column not in frame.columns:
                raise ValueError(f"La regla requiere '{name}', pero no existe una columna validada para ese concepto")
            return pd.to_numeric(frame[column], errors="coerce").fillna(0.0)

        def ev(node):
            if isinstance(node, ast.Expression):
                return ev(node.body)
            if isinstance(node, ast.Name):
                return series_for_name(node.id)
            if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
                return float(node.value)
            if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
                value = ev(node.operand)
                return value if isinstance(node.op, ast.UAdd) else -value
            if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
                left, right = ev(node.left), ev(node.right)
                if isinstance(node.op, ast.Add): return left + right
                if isinstance(node.op, ast.Sub): return left - right
                if isinstance(node.op, ast.Mult): return left * right
                if isinstance(node.op, ast.Div):
                    if isinstance(right, pd.Series):
                        return left.div(right.replace(0, pd.NA)).replace([float("inf"), float("-inf")], pd.NA)
                    if right == 0:
                        raise ValueError("Division entre cero en regla empresarial")
                    return left / right
            raise ValueError(f"Operacion no permitida en regla empresarial: {type(node).__name__}")

        result = ev(tree)
        if isinstance(result, pd.Series):
            return pd.to_numeric(result, errors="coerce")
        return pd.Series([float(result)] * len(frame), index=frame.index, dtype="float64")

    def knowledge_context(
        self,
        principal: Principal,
        question: str,
        *,
        columns: Optional[Sequence[str]] = None,
        inferred_roles: Optional[Dict[str, Any]] = None,
        area: Optional[str] = None,
        on_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        roles, definitions = self.semantic_overrides(principal, columns or [], inferred_roles or {}, on_date=on_date)
        rules = self.relevant_rules(principal, question, area=area, on_date=on_date)
        return {
            "precedence": list(PRECEDENCE),
            "rules": rules,
            "semantic_definitions": definitions,
            "roles": roles,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
