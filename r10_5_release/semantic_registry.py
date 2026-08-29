from __future__ import annotations

import contextlib
import contextvars
import re
import unicodedata
from typing import Any, Dict, Iterator, List, Optional, Sequence

import pandas as pd

from .precedence_engine import PrecedenceEngine
from .security import Principal

# Contrato semántico compartido por StructuredData, BI productivo y dashboards.
CANONICAL_ROLES = (
    'date','invoice','customer_id','customer','product_id','product','line','zone',
    'seller_id','seller','supplier','quantity','unit_price','revenue','total_cost',
    'cost_without_freight','product_cost','other_cost','freight','freight_short',
    'freight_long','freight_transfer','warehouse','origin_city','destination_city',
    'category','country','actual','budget','previous','period_start','period_end'
)

# Alias internos que históricamente usan módulos distintos.
ROLE_BRIDGES = {
    'sales':'revenue', 'revenue':'revenue',
    'cost':'total_cost', 'total_cost':'total_cost',
    'price':'unit_price', 'unit_price':'unit_price',
    'profit':'profit',
    'freight':'freight',
}

_CURRENT_CONTEXT: contextvars.ContextVar[Optional[Dict[str, Any]]] = contextvars.ContextVar(
    'ia_enterprise_semantic_context', default=None
)


def _norm(value: Any) -> str:
    s=str(value or '').strip().lower()
    s=''.join(c for c in unicodedata.normalize('NFD',s) if unicodedata.category(c)!='Mn')
    return re.sub(r'[^a-z0-9_]+','_',s).strip('_')


def bridge_roles(roles: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Normaliza roles de cualquier motor al contrato canónico sin borrar extras."""
    src=dict(roles or {})
    out=dict(src)
    for key,value in list(src.items()):
        target=ROLE_BRIDGES.get(str(key))
        if target and value and not out.get(target):
            out[target]=value
    # También ofrece alias inversos para consumidores legacy.
    if out.get('revenue') and not out.get('sales'): out['sales']=out['revenue']
    if out.get('total_cost') and not out.get('cost'): out['cost']=out['total_cost']
    if out.get('unit_price') and not out.get('price'): out['price']=out['unit_price']
    return out


def merge_context_roles(inferred: Dict[str, Any], semantic_context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    out=bridge_roles(inferred)
    ctx_roles=bridge_roles((semantic_context or {}).get('roles') or {})
    # El contexto gobernado ya fue validado por empresa/usuario y tiene precedencia.
    for role,column in ctx_roles.items():
        if column:
            out[role]=column
    return bridge_roles(out)


def current_context() -> Optional[Dict[str, Any]]:
    value=_CURRENT_CONTEXT.get()
    return dict(value) if isinstance(value,dict) else None


class SemanticRegistry:
    def __init__(self, precedence: PrecedenceEngine):
        self.precedence=precedence

    def resolve(
        self,
        principal: Principal,
        columns: Sequence[str],
        inferred_roles: Optional[Dict[str, Any]]=None,
        *,
        on_date: Optional[str]=None,
    ) -> Dict[str, Any]:
        inferred=bridge_roles(inferred_roles)
        governed, applied=self.precedence.semantic_overrides(
            principal, list(map(str,columns)), inferred, on_date=on_date
        )
        roles=bridge_roles(governed)
        # Una definición VALIDADA debe sustituir incluso aliases equivalentes que
        # ya tuvieran una inferencia (sales -> revenue, cost -> total_cost, etc.).
        for item in applied:
            source_role=str(item.get('role') or '')
            target_role=ROLE_BRIDGES.get(source_role, source_role)
            physical=item.get('physical_name')
            if target_role and physical:
                roles[target_role]=physical
                if target_role=='revenue': roles['sales']=physical
                elif target_role=='total_cost': roles['cost']=physical
                elif target_role=='unit_price': roles['price']=physical
        # Mantener exclusivamente columnas reales para roles físicos.
        existing={str(c) for c in columns}
        clean={}
        for role,col in roles.items():
            if col is None or col in existing:
                clean[role]=col
        return {
            'version':'r10.5',
            'company_id':principal.company_id,
            'user_id':principal.user_id,
            'roles':clean,
            'validated_definitions':applied,
            'precedence':'validated_semantic_definition > system_inference',
        }

    def resolve_frame(self, principal: Principal, df: pd.DataFrame, inferred_roles: Optional[Dict[str, Any]]=None, *, on_date: Optional[str]=None) -> Dict[str, Any]:
        return self.resolve(principal, list(map(str,df.columns)), inferred_roles, on_date=on_date)

    @contextlib.contextmanager
    def bind(self, principal: Principal, df: pd.DataFrame, inferred_roles: Optional[Dict[str, Any]]=None, *, on_date: Optional[str]=None) -> Iterator[Dict[str, Any]]:
        ctx=self.resolve_frame(principal,df,inferred_roles,on_date=on_date)
        token=_CURRENT_CONTEXT.set(ctx)
        try:
            yield ctx
        finally:
            _CURRENT_CONTEXT.reset(token)
