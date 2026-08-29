from __future__ import annotations
import re, unicodedata
from typing import Any, Dict, Optional

VERSION = "r10.13a.2-v3"

def norm(v: Any) -> str:
    s = str(v or "").strip().lower()
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9_]+", "_", s).strip("_")

def _is_invalid_freight(column: Any) -> bool:
    n = norm(column)
    return bool(n) and (
        "sin_flete" in n
        or "without_freight" in n
        or "excluding_freight" in n
        or n in {"cost_without_freight","costo_sin_flete"}
    )

def _is_invalid_supplier(column: Any) -> bool:
    n = norm(column)
    if not n:
        return False
    return (
        "contrato_proveedor" in n
        or "supplier_contract" in n
        or "vendor_contract" in n
        or n in {"contratoproveedor","suppliercontract","vendorcontract"}
    )

def sanitize_legacy_semantic_roles(
    roles: Dict[str, Any],
    *,
    strict_usable: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Sanitize contradictory inferred semantic roles.

    Important: strict_usable here is still system inference, not governed truth.
    Therefore negative semantic evidence has precedence over both legacy and
    strict fallback inference.
    """
    out = dict(roles or {})
    strict = dict(strict_usable or {})

    strict_freight = strict.get("freight")
    if strict_freight and not _is_invalid_freight(strict_freight):
        out["freight"] = strict_freight
    elif _is_invalid_freight(out.get("freight")) or _is_invalid_freight(strict_freight):
        out["freight"] = None

    strict_supplier = strict.get("supplier")
    if strict_supplier and not _is_invalid_supplier(strict_supplier):
        out["supplier"] = strict_supplier
    elif _is_invalid_supplier(out.get("supplier")) or _is_invalid_supplier(strict_supplier):
        out["supplier"] = None

    return out
