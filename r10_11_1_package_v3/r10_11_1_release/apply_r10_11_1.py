from __future__ import annotations

import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()
scripts = root / "scripts"
uengine = scripts / "universal_prompt_engine.py"
universal = scripts / "analizador_universal.py"
bi = scripts / "bi_productivo.py"
app = scripts / "analizador_app.py"
version = root / "VERSION.txt"

def read(p):
    return p.read_text(encoding="utf-8-sig")

def write(p, s):
    p.write_text(s, encoding="utf-8")

# 1) Conservative date detection.
t = read(uengine)
old = '''def _is_date(s: pd.Series) -> bool:
    if pd.api.types.is_datetime64_any_dtype(s):
        return True
    sample = s.dropna().head(200)
    if sample.empty:
        return False
    parsed = pd.to_datetime(sample, errors="coerce", dayfirst=False)
    return parsed.notna().mean() >= 0.85
'''
new = '''def _is_date(s: pd.Series) -> bool:
    if pd.api.types.is_datetime64_any_dtype(s):
        return True
    if pd.api.types.is_numeric_dtype(s):
        return False
    sample = s.dropna().astype(str).str.strip().head(200)
    if sample.empty:
        return False
    # Parse only values that already look like calendar dates.
    looks = sample.str.match(r"^(?:\\d{4}[-/]\\d{1,2}[-/]\\d{1,2}|\\d{1,2}[-/]\\d{1,2}[-/]\\d{2,4})(?:\\s|$)")
    if float(looks.mean()) < 0.85:
        return False
    parsed = pd.to_datetime(sample[looks], errors="coerce", dayfirst=False)
    return float(parsed.notna().mean()) >= 0.85
'''
if old in t:
    t = t.replace(old, new, 1)
elif "Parse only values that already look like calendar dates." not in t:
    raise RuntimeError("No se pudo localizar _is_date para aplicar el hotfix")

t = t.replace(
    '"excel": ("excel", "xlsx", "libro analitico", "libro analítico"),',
    '"excel": ("generar excel", "genera excel", "reporte excel", "excel analitico", "excel analítico", "libro analitico", "libro analítico", "salida xlsx"),'
)
write(uengine, t)

# 2) Strict data contract.
t = read(universal)
if "from data_contract import validate_workbook_contract" not in t:
    t = t.replace(
        "import dashboard_dynamic as dd\n",
        "import dashboard_dynamic as dd\nfrom data_contract import validate_workbook_contract, DataContractError\n",
        1,
    )

needle = 'def load_tabular(path: Path, prompt: str = "") -> Tuple[pd.DataFrame, Dict[str, Any]]:\n    ext = path.suffix.lower()\n'
replacement = 'def load_tabular(path: Path, prompt: str = "") -> Tuple[pd.DataFrame, Dict[str, Any]]:\n    contract = validate_workbook_contract(path, prompt)\n    ext = path.suffix.lower()\n'
if needle in t:
    t = t.replace(needle, replacement, 1)

anchor = '    if not frames:\n        raise ValueError("El libro no contiene hojas legibles con datos tabulares.")\n\n'
block = '''    requested_sheet = contract.get("explicit_sheet")
    if requested_sheet:
        for _sheet, _frame, _header_idx in frames:
            if norm(_sheet) == norm(requested_sheet):
                meta["hoja_analizada"] = _sheet
                meta["data_contract"] = contract
                return _frame, meta
        raise DataContractError(
            f'La hoja requerida "{requested_sheet}" no pudo cargarse como tabla.',
            code="SOURCE_SHEET_UNREADABLE",
            details={"requested_sheet": requested_sheet},
        )

'''
if 'requested_sheet = contract.get("explicit_sheet")' not in t:
    if anchor not in t:
        raise RuntimeError("No se pudo localizar punto de selección de hoja")
    t = t.replace(anchor, anchor + block, 1)
write(universal, t)

# 3) BI priorities.
t = read(bi)
profit_anchor = "    r['total_cost'] = _first_existing(df, ['Costo','Costo_Total','Total_Cost','Cost'], ['costo total','total cost'])\n"
if "r['profit'] =" not in t:
    t = t.replace(
        profit_anchor,
        profit_anchor +
        "    r['profit'] = _first_existing(df, ['Utilidad','Ganancia','Profit','Beneficio'], ['utilidad','ganancia','profit','beneficio'])\n" +
        "    r['freight_total'] = _first_existing(df, ['Costo_Flete','Costo Flete','Freight_Cost','Freight Cost'], ['costo flete','freight cost'], ['corto','largo','traspaso'])\n" +
        "    r['supplier'] = _first_existing(df, ['Proveedor','Supplier','Vendor'], ['proveedor','supplier','vendor'], ['cod','codigo',' id'])\n" +
        "    r['week'] = _first_existing(df, ['Semana','Week'], ['semana','week'])\n" +
        "    r['product_group'] = _first_existing(df, ['ctrl_alm','Agrupador','Grupo_Producto'], ['ctrl alm','agrupador','grupo producto'])\n",
        1,
    )

old_freight = '''    freight_cols = [roles.get('freight_short'), roles.get('freight_long'), roles.get('freight_transfer')]
    freight_cols = [c for c in freight_cols if c]
    if freight_cols:
        freight = pd.Series(0.0, index=work.index)
        any_value = pd.Series(False, index=work.index)
        for c in freight_cols:
            n = _num(work[c])
            any_value |= n.notna()
            freight = freight.add(n.fillna(0), fill_value=0)
        work['_flete'] = freight.where(any_value)
        derived['flete'] = ' + '.join(freight_cols)
'''
new_freight = '''    freight_cols = [roles.get('freight_short'), roles.get('freight_long'), roles.get('freight_transfer')]
    freight_cols = [c for c in freight_cols if c]
    freight_total = roles.get('freight_total')
    if freight_total:
        work['_flete'] = _num(work[freight_total])
        derived['flete'] = freight_total
        derived['flete_fuente'] = 'columna_real'
    elif freight_cols:
        freight = pd.Series(0.0, index=work.index)
        any_value = pd.Series(False, index=work.index)
        for c in freight_cols:
            n = _num(work[c])
            any_value |= n.notna()
            freight = freight.add(n.fillna(0), fill_value=0)
        work['_flete'] = freight.where(any_value)
        derived['flete'] = ' + '.join(freight_cols)
        derived['flete_fuente'] = 'componentes'
'''
if old_freight in t:
    t = t.replace(old_freight, new_freight, 1)

old_profit = '''    if '_ventas' in work.columns and '_costo' in work.columns:
        work['_utilidad'] = work['_ventas'] - work['_costo']
        derived['utilidad'] = 'ventas - costo total'
'''
new_profit = '''    profit_col = roles.get('profit')
    if profit_col:
        work['_utilidad'] = _num(work[profit_col])
        derived['utilidad'] = profit_col
        derived['utilidad_fuente'] = 'columna_real'
        if '_ventas' in work.columns and '_costo' in work.columns:
            calc = work['_ventas'] - work['_costo']
            coverage, median_rel = _coverage_ratio(work['_utilidad'], calc)
            derived['validacion_utilidad'] = {
                'formula_comparada': 'ventas - costo total',
                'cobertura': coverage,
                'error_relativo_mediano': median_rel,
            }
    elif '_ventas' in work.columns and '_costo' in work.columns:
        work['_utilidad'] = work['_ventas'] - work['_costo']
        derived['utilidad'] = 'ventas - costo total'
        derived['utilidad_fuente'] = 'derivada_por_ausencia'
'''
if old_profit in t:
    t = t.replace(old_profit, new_profit, 1)
elif "derived['utilidad_fuente'] = 'columna_real'" not in t:
    raise RuntimeError("No se pudo parchear Utilidad")

t = t.replace(
    "excel_terms = ('excel','excel analitico','excel analítico','xlsx','libro analitico','libro analítico')",
    "excel_terms = ('generar excel','genera excel','reporte excel','excel analitico','excel analítico','libro analitico','libro analítico','salida xlsx')"
)
write(bi, t)

# 4) Structured error logging.
t = read(app)
if "import traceback" not in t:
    t = t.replace("import shutil\n", "import shutil\nimport traceback\n", 1)

old_except = '    except Exception as e:\n        return JSONResponse({"ok": False, "error": f"{type(e).__name__}: {e}"}, status_code=500)\n'
new_except = '''    except Exception as e:
        stage = getattr(e, "stage", "analyze_file")
        code = getattr(e, "code", "INTERNAL_ANALYZER_ERROR")
        details = getattr(e, "details", None)
        payload = {
            "ok": False,
            "error": f"{type(e).__name__}: {e}",
            "code": code,
            "stage": stage,
            "details": details,
        }
        try:
            log_dir = ROOT / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            with (log_dir / "analizador.err.log").open("a", encoding="utf-8") as fh:
                fh.write("\\n=== ANALYZER ERROR ===\\n")
                fh.write(f"stage={stage} code={code} file={getattr(file, 'filename', '')}\\n")
                fh.write(traceback.format_exc())
                fh.write("\\n")
        except Exception:
            pass
        status = 422 if code in {"SOURCE_SHEET_NOT_FOUND","DECLARED_COLUMNS_MISSING","SOURCE_SHEET_UNREADABLE","DATA_CONTRACT_ERROR"} else 500
        return JSONResponse(payload, status_code=status)
'''
if old_except in t:
    t = t.replace(old_except, new_except, 1)
elif "ANALYZER ERROR" not in t:
    raise RuntimeError("No se pudo parchear manejo de errores")
write(app, t)

current_version = version.read_text(encoding="utf-8").strip() if version.exists() else ""
if "r10.12" in current_version.lower():
    final_version = "8.5.5-r10.12-controlled-finetune-dataset+hotfix-r10.11.1-data-contract"
else:
    final_version = "8.5.5-r10.11.1-data-contract-hotfix"
version.write_text(final_version + "\n", encoding="utf-8")
print("R10.11.1 patch OK")
print("Version preservada:", final_version)
