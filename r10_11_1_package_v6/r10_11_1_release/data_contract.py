from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

VERSION = "8.5.5-r10.11.1-data-contract-hotfix"

class DataContractError(ValueError):
    def __init__(self, message: str, *, code: str = "DATA_CONTRACT_ERROR", details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.code = code
        self.details = details or {}
        self.stage = "data_contract"

def norm(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")
    text = re.sub(r"[^a-z0-9_]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()

def extract_explicit_sheet(prompt: str) -> Optional[str]:
    raw = str(prompt or "")
    patterns = [
        r"(?is)\bla\s+hoja\s*:\s*[\r\n ]*([A-Za-z0-9_. -]{1,60}?)[\r\n ]+(?:es\s+)?(?:la\s+)?(?:base\s+de\s+datos\s+principal|[úu]nica\s+fuente\s+de\s+verdad|fuente\s+[úu]nica)",
        r"(?is)\bhoja\s+([A-Za-z0-9_. -]{1,60}?)\s+(?:es\s+)?(?:la\s+)?(?:fuente|base\s+de\s+datos\s+principal|[úu]nica\s+fuente)",
        r"(?is)\busar\s+(?:la\s+)?hoja\s+([A-Za-z0-9_. -]{1,60}?)(?:[\r\n.,;]|$)",
    ]
    for pattern in patterns:
        m = re.search(pattern, raw)
        if m:
            value = re.sub(r"\s+", " ", m.group(1)).strip(" .:-\t\r\n")
            if value:
                return value
    m = re.search(r"(?is)\bla\s+hoja\s*:\s*[\r\n]+(?:\s*[\r\n]+)*([^\r\n]{1,60})[\r\n]+(?:\s*[\r\n]+)*es\s+la\s+base\s+de\s+datos\s+principal", raw)
    return m.group(1).strip() if m else None

def extract_declared_columns(prompt: str) -> List[str]:
    raw = str(prompt or "")
    m = re.search(r"(?is)COLUMNAS\s+DE\s+[A-Za-z0-9_. -]+\s*\n\s*=+\s*\n(.*?)(?=\n\s*=+\s*\n)", raw)
    if not m:
        return []
    out = []
    for line in m.group(1).splitlines():
        line = line.strip().strip("*-•` ")
        if not line or line.startswith("="):
            continue
        if re.match(r"^\d+[.)]\s", line):
            continue
        if len(line) <= 80 and re.match(r"^[A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9_ %/.-]+$", line):
            out.append(line)
    seen, clean = set(), []
    for value in out:
        k = norm(value)
        if k and k not in seen:
            seen.add(k)
            clean.append(value)
    return clean

def match_sheet(sheet_names: List[str], requested: str) -> Optional[str]:
    rn = norm(requested)
    for name in sheet_names:
        if norm(name) == rn:
            return name
    return None

def validate_workbook_contract(path: str | Path, prompt: str) -> Dict[str, Any]:
    path = Path(path)
    if path.suffix.lower() not in {".xlsx", ".xlsm", ".xls", ".xlsb"}:
        return {"ok": True, "explicit_sheet": None, "available_sheets": ["TABULAR"], "declared_columns": [], "missing_columns": []}

    xls = pd.ExcelFile(path)
    try:
        sheets = [str(x) for x in xls.sheet_names]
        requested = extract_explicit_sheet(prompt)
        if not requested:
            return {"ok": True, "explicit_sheet": None, "available_sheets": sheets, "declared_columns": [], "missing_columns": []}
        matched = match_sheet(sheets, requested)
        if not matched:
            raise DataContractError(
                f'El prompt establece la hoja "{requested}" como fuente única, pero el archivo no la contiene. Hojas disponibles: {", ".join(sheets)}.',
                code="SOURCE_SHEET_NOT_FOUND",
                details={"requested_sheet": requested, "available_sheets": sheets},
            )
        declared = extract_declared_columns(prompt)
        header = pd.read_excel(xls, sheet_name=matched, nrows=0)
        actual = [str(c).strip() for c in header.columns]
        amap = {norm(c): c for c in actual}
        missing = [c for c in declared if norm(c) not in amap]
        if missing:
            raise DataContractError(
                f'La hoja "{matched}" existe, pero faltan {len(missing)} columnas declaradas por el prompt: {", ".join(missing[:20])}.',
                code="DECLARED_COLUMNS_MISSING",
                details={"requested_sheet": matched, "missing_columns": missing, "actual_columns": actual},
            )
        return {
            "ok": True, "explicit_sheet": matched, "available_sheets": sheets,
            "declared_columns": declared, "missing_columns": [], "actual_columns": actual,
        }
    finally:
        try:
            xls.close()
        except Exception:
            pass
