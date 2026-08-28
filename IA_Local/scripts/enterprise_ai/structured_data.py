from __future__ import annotations

import hashlib
import json
import re
import unicodedata
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import pandas as pd

from .database import Database, utcnow
from .providers import LLMProvider
from .security import Principal, scope_clause


def norm(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


ROLE_PATTERNS = {
    "date": ["fecha", "date", "invoice date", "created at"],
    "product": ["producto", "product", "description", "descripcion", "articulo", "item", "sku", "stockcode"],
    "customer": ["cliente", "customer"],
    "supplier": ["proveedor", "supplier", "vendor"],
    "quantity": ["cantidad", "quantity", "qty", "unidades", "units"],
    "price": ["precio venta", "unit price", "price", "precio"],
    "sales": ["ventas", "venta total", "sales", "revenue", "importe", "amount", "total"],
    "cost": ["costo compra", "cost", "costo", "compra", "purchase"],
    "freight": ["flete", "freight", "shipping"],
    "country": ["pais", "country"],
    "invoice": ["factura", "invoice", "folio", "ticket"],
}


def infer_roles(columns: Sequence[str]) -> Dict[str, Optional[str]]:
    result = {key: None for key in ROLE_PATTERNS}
    for role, patterns in ROLE_PATTERNS.items():
        candidates = []
        for column in columns:
            ncol = norm(column)
            score = max([100 if ncol == p else 70 if p in ncol else 0 for p in patterns] or [0])
            if score:
                candidates.append((score, -len(ncol), column))
        if candidates:
            result[role] = max(candidates)[2]
    return result


def hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


class StructuredDataService:
    def __init__(self, db: Database, llm: Optional[LLMProvider] = None):
        self.db = db
        self.llm = llm

    def _inspect(self, path: Path) -> Tuple[List[str], Dict[str, Optional[str]], Dict[str, Any]]:
        ext = path.suffix.lower()
        if ext == ".csv":
            df = pd.read_csv(path, nrows=100, low_memory=False)
            meta = {"sheets": ["CSV"], "default_sheet": "CSV"}
        else:
            try:
                xls = pd.ExcelFile(path, engine="calamine")
            except Exception:
                xls = pd.ExcelFile(path)
            try:
                sheet = xls.sheet_names[0]
                df = pd.read_excel(xls, sheet_name=sheet, nrows=100)
                meta = {"sheets": list(map(str, xls.sheet_names)), "default_sheet": str(sheet)}
            finally:
                try:
                    xls.close()
                except Exception:
                    pass
        columns = list(map(str, df.columns))
        return columns, infer_roles(columns), meta

    def register(
        self,
        principal: Principal,
        path: str | Path,
        *,
        name: Optional[str] = None,
        scope: str = "company",
        file_hash: Optional[str] = None,
        roles: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        path = Path(path).resolve()
        columns, inferred_roles, meta = self._inspect(path)
        roles = roles or inferred_roles
        file_hash = file_hash or hash_file(path)
        owner = principal.user_id if scope == "user" else None
        dataset_name = name or path.name
        existing = self.db.one(
            "SELECT * FROM datasets WHERE company_id=? AND scope=? AND ((user_id IS NULL AND ? IS NULL) OR user_id=?) AND name=? AND active=1",
            (principal.company_id, scope, owner, owner, dataset_name),
        )
        now = utcnow()
        dataset_id = existing["id"] if existing else str(uuid.uuid4())
        payload = (
            str(path), file_hash, json.dumps(columns, ensure_ascii=False), json.dumps(roles, ensure_ascii=False),
            json.dumps(meta, ensure_ascii=False), now, dataset_id,
        )
        if existing:
            self.db.execute(
                "UPDATE datasets SET path=?,file_hash=?,columns_json=?,roles_json=?,metadata_json=?,updated_at=? WHERE id=?",
                payload,
            )
        else:
            self.db.execute(
                "INSERT INTO datasets(id,company_id,user_id,scope,name,path,file_hash,columns_json,roles_json,metadata_json,active,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    dataset_id, principal.company_id, owner, scope, dataset_name, str(path), file_hash,
                    json.dumps(columns, ensure_ascii=False), json.dumps(roles, ensure_ascii=False),
                    json.dumps(meta, ensure_ascii=False), 1, now, now,
                ),
            )
        self.db.audit("dataset.register", principal.company_id, principal.user_id, "dataset", dataset_id, details={"name": dataset_name, "columns": len(columns)})
        return {"dataset_id": dataset_id, "name": dataset_name, "columns": columns, "roles": roles, "metadata": meta}

    def list(self, principal: Principal) -> List[Dict[str, Any]]:
        clause, args = scope_clause(principal)
        rows = self.db.query(f"SELECT * FROM datasets WHERE {clause} AND active=1 ORDER BY updated_at DESC", args)
        output = []
        for row in rows:
            data = dict(row)
            data["columns"] = json.loads(data.pop("columns_json") or "[]")
            data["roles"] = json.loads(data.pop("roles_json") or "{}")
            data["metadata"] = json.loads(data.pop("metadata_json") or "{}")
            output.append(data)
        return output

    def _choose(self, principal: Principal, prompt: str) -> Optional[Dict[str, Any]]:
        datasets = self.list(principal)
        if not datasets:
            return None
        pnorm = norm(prompt)
        tokens = {token for token in pnorm.split() if len(token) > 2}

        def score(dataset: Dict[str, Any]) -> int:
            blob = norm(dataset["name"] + " " + " ".join(dataset["columns"]))
            return sum(4 for token in tokens if token in blob) + (10 if norm(dataset["name"]).replace(" ", "") in pnorm.replace(" ", "") else 0)

        return max(datasets, key=score)

    def _load(self, dataset: Dict[str, Any]) -> Tuple[pd.DataFrame, str]:
        path = Path(dataset["path"])
        if path.suffix.lower() == ".csv":
            return pd.read_csv(path, low_memory=False), "CSV"
        try:
            xls = pd.ExcelFile(path, engine="calamine")
        except Exception:
            xls = pd.ExcelFile(path)
        schemas: Dict[Tuple[str, ...], List[Tuple[str, pd.DataFrame]]] = {}
        try:
            for sheet in xls.sheet_names:
                try:
                    frame = pd.read_excel(xls, sheet_name=sheet)
                    schemas.setdefault(tuple(map(str, frame.columns)), []).append((str(sheet), frame))
                except Exception:
                    continue
        finally:
            try:
                xls.close()
            except Exception:
                pass
        if not schemas:
            raise ValueError("No se pudo leer ninguna hoja")
        group = max(schemas.values(), key=lambda entries: sum(len(entry[1]) for entry in entries))
        return pd.concat([entry[1] for entry in group], ignore_index=True), ", ".join(entry[0] for entry in group)

    def _heuristic_plan(self, prompt: str, roles: Dict[str, Any]) -> Dict[str, Any]:
        p = norm(prompt)
        plan = {"operation": "sum", "metric": "sales", "group_by": None, "year": None, "filters": []}
        year_match = re.search(r"\b(20\d{2})\b", p)
        plan["year"] = int(year_match.group(1)) if year_match else None
        if any(x in p for x in ["promedio", "average", "media"]):
            plan["operation"] = "mean"
        if any(x in p for x in ["cuantas", "cuantos", "numero de", "conteo", "count"]):
            plan["operation"] = "count"
        if any(x in p for x in ["top", "mayores", "mejores", "principales"]):
            plan["operation"] = "top"
        if "unidades" in p or "cantidad" in p:
            plan["metric"] = "quantity"
        if "costo" in p or "compras" in p:
            plan["metric"] = "cost"
        if "utilidad" in p or "rentabilidad" in p or "margen" in p:
            plan["metric"] = "profit"
        if "producto" in p or "articulo" in p:
            plan["group_by"] = "product"
        elif "cliente" in p:
            plan["group_by"] = "customer"
        elif "proveedor" in p:
            plan["group_by"] = "supplier"
        elif "pais" in p:
            plan["group_by"] = "country"
        if roles.get("product"):
            quoted = re.findall(r"[\"']([^\"']{2,80})[\"']", prompt)
            if quoted:
                plan["filters"].append({"role": "product", "value": quoted[0]})
            else:
                match = re.search(r"\bde\s+([a-z0-9áéíóúñ _-]{2,60}?)(?:\s+durante|\s+en\s+20\d{2}|\s+del\s+20\d{2}|\?|$)", prompt, re.I)
                if match:
                    value = match.group(1).strip()
                    if value.lower() not in {"ventas", "compra", "compras", "utilidad", "rentabilidad"}:
                        plan["filters"].append({"role": "product", "value": value})
        return plan

    def _llm_plan(self, prompt: str, dataset: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not self.llm:
            return None
        system = (
            "Devuelve SOLO JSON valido para calcular datos tabulares. No inventes columnas ni valores de filtro. "
            "Formato: {\"operation\":\"sum|mean|count|top\",\"metric\":\"sales|quantity|cost|profit|columna exacta\","
            "\"group_by\":\"product|customer|supplier|country|columna exacta|null\",\"year\":2025|null,"
            "\"filters\":[{\"role\":\"product|customer|supplier|country|columna exacta\",\"value\":\"texto literal de la pregunta\"}]}. "
            "El codigo calcula; tu solo planeas."
        )
        try:
            raw = self.llm.chat(
                [
                    {"role": "system", "content": system},
                    {"role": "user", "content": json.dumps({"question": prompt, "columns": dataset["columns"], "roles": dataset["roles"]}, ensure_ascii=False)},
                ],
                json_mode=True,
                max_tokens=250,
                temperature=0,
            )
            obj = json.loads(raw)
            return obj if isinstance(obj, dict) else None
        except Exception:
            return None

    def query(self, principal: Principal, prompt: str, memories: Optional[Sequence[Dict[str, Any]]] = None) -> Optional[Dict[str, Any]]:
        dataset = self._choose(principal, prompt)
        if not dataset:
            return None
        plan = self._llm_plan(prompt, dataset) or self._heuristic_plan(prompt, dataset["roles"])
        pnorm = norm(prompt)
        safe_filters = []
        for item in plan.get("filters", []) if isinstance(plan.get("filters"), list) else []:
            value = str(item.get("value", "")).strip()
            if value and norm(value) in pnorm:
                safe_filters.append(item)
        plan["filters"] = safe_filters
        df, sheet = self._load(dataset)
        roles = infer_roles(list(map(str, df.columns)))
        work = df.copy()
        if roles.get("date"):
            work["__date"] = pd.to_datetime(work[roles["date"]], errors="coerce")
        if roles.get("sales"):
            work["__sales"] = pd.to_numeric(work[roles["sales"]], errors="coerce")
        elif roles.get("quantity") and roles.get("price"):
            work["__sales"] = pd.to_numeric(work[roles["quantity"]], errors="coerce") * pd.to_numeric(work[roles["price"]], errors="coerce")
        if roles.get("quantity"):
            work["__quantity"] = pd.to_numeric(work[roles["quantity"]], errors="coerce")
        if roles.get("cost"):
            cost = pd.to_numeric(work[roles["cost"]], errors="coerce")
            if roles.get("quantity") and "unit" in norm(roles["cost"]):
                cost = cost * pd.to_numeric(work[roles["quantity"]], errors="coerce")
            work["__cost"] = cost
        rule_used = None
        if plan.get("metric") == "profit":
            for memory in memories or []:
                c = norm(memory.get("content"))
                if "utilidad" in c and "venta" in c and ("compra" in c or "costo" in c):
                    rule_used = memory.get("content")
                    break
            if "__sales" in work and "__cost" in work:
                profit = work["__sales"] - work["__cost"]
                if roles.get("freight"):
                    profit = profit - pd.to_numeric(work[roles["freight"]], errors="coerce").fillna(0)
                work["__profit"] = profit
        if plan.get("year") and "__date" in work:
            work = work.loc[work["__date"].dt.year == int(plan["year"])]
        for item in plan["filters"]:
            role = item.get("role")
            column = roles.get(role) if role in roles else (role if role in work.columns else None)
            if column:
                work = work.loc[work[column].astype(str).str.contains(re.escape(str(item["value"])), case=False, na=False)]
        metric = plan.get("metric", "sales")
        metric_column = {"sales": "__sales", "quantity": "__quantity", "cost": "__cost", "profit": "__profit"}.get(metric, metric if metric in work.columns else None)
        operation = plan.get("operation", "sum")
        group = plan.get("group_by")
        group_column = roles.get(group) if group in roles else (group if group in work.columns else None)
        source = {
            "type": "dataset",
            "file": dataset["name"],
            "sheet": sheet,
            "rows_used": int(len(work)),
            "filters": plan.get("filters", []),
            "year": plan.get("year"),
            "calculation": "python/pandas",
        }
        if operation in {"sum", "mean"}:
            if not metric_column or metric_column not in work or not pd.to_numeric(work[metric_column], errors="coerce").notna().any():
                return {"insufficient": True, "reason": f"No existe una metrica calculable para {metric} en {dataset['name']}.", "source": source, "plan": plan}
            series = pd.to_numeric(work[metric_column], errors="coerce")
            value = float(series.sum()) if operation == "sum" else float(series.mean())
            return {"insufficient": False, "value": value, "metric": metric, "operation": operation, "rows_used": int(len(work)), "source": source, "plan": plan, "rule_used": rule_used}
        if operation == "count":
            return {"insufficient": False, "value": int(len(work)), "metric": "rows", "operation": "count", "source": source, "plan": plan}
        if operation == "top" and group_column:
            if metric_column and metric_column in work:
                table = work.assign(__metric=pd.to_numeric(work[metric_column], errors="coerce")).groupby(group_column, dropna=False)["__metric"].sum(min_count=1).sort_values(ascending=False).head(10).reset_index(name="value")
            else:
                table = work.groupby(group_column, dropna=False).size().sort_values(ascending=False).head(10).reset_index(name="value")
            return {"insufficient": False, "table": table.to_dict("records"), "metric": metric, "operation": "top", "source": source, "plan": plan}
        return None
