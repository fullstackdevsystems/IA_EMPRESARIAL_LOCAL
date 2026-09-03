from __future__ import annotations

"""Reportes ejecutivos profesionales para IA Local Empresarial V7."""

from io import BytesIO
import math
import re
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from enterprise_deliverable_manifest import deliverable_manifest_component_rows, deliverable_manifest_summary_rows

NAVY="#0B1F33"; BLUE="#0F62FE"; TEAL="#007D79"; GREEN="#198038"; ORANGE="#FF832B"; RED="#DA1E28"; PURPLE="#6929C4"
LIGHT="#F4F7FB"; PALE_BLUE="#EDF5FF"; PALE_GREEN="#DEFBE6"; PALE_ORANGE="#FFF2E8"; PALE_RED="#FFF1F1"; MID="#697077"; BORDER="#DDE1E6"; WHITE="#FFFFFF"


def _norm(x: Any) -> str:
    s=str(x or "").strip().lower()
    s=re.sub(r"[^a-z0-9áéíóúüñ%]+"," ",s)
    return re.sub(r"\s+"," ",s).strip()


def infer_domain(work: pd.DataFrame, roles: Dict[str, Optional[str]]) -> str:
    cols=" | ".join(_norm(c) for c in work.columns)
    if "_ventas" in work.columns: return "comercial"
    if any(k in cols for k in ("inventario","existencia","stock","almacen","warehouse")): return "inventario"
    if any(k in cols for k in ("empleado","employee","departamento","nomina","salary","sueldo")): return "recursos_humanos"
    if any(k in cols for k in ("proveedor","supplier","purchase","compra","orden compra")): return "compras"
    if any(k in cols for k in ("cuenta","balance","debe","haber","ledger")): return "financiero"
    if any(k in cols for k in ("flete","freight","ruta","route","entrega","delivery","shipment")): return "logistica"
    return "general"


def domain_title(domain: str) -> str:
    return {"comercial":"Reporte Ejecutivo Comercial","inventario":"Reporte Ejecutivo de Inventarios","recursos_humanos":"Reporte Ejecutivo de Recursos Humanos","compras":"Reporte Ejecutivo de Compras","financiero":"Reporte Ejecutivo Financiero","logistica":"Reporte Ejecutivo de Logística","general":"Reporte Ejecutivo de Análisis de Datos"}.get(domain,"Reporte Ejecutivo de Análisis de Datos")


def _metric_dict(sections: Dict[str,pd.DataFrame], name: str) -> Dict[str,Any]:
    df=sections.get(name)
    if df is None or df.empty or len(df.columns)<2: return {}
    return {str(r.iloc[0]):r.iloc[1] for _,r in df.iterrows()}


def _float(v: Any) -> Optional[float]:
    try:
        if v is None or pd.isna(v): return None
        return float(v)
    except Exception: return None


def _compact(v: Any, decimals: int=2) -> str:
    x=_float(v)
    if x is None: return "N/D"
    sign="-" if x<0 else ""; a=abs(x)
    if a>=1_000_000_000: return f"{sign}{a/1_000_000_000:.2f} B"
    if a>=1_000_000: return f"{sign}{a/1_000_000:.2f} M"
    if a>=1_000: return f"{sign}{a/1_000:.1f} K"
    return f"{x:,.{decimals}f}"


def _fmt(v: Any, kind: str="number") -> str:
    if v is None: return "N/D"
    try:
        if pd.isna(v): return "N/D"
    except Exception: pass
    if kind=="id":
        try:
            x=float(v)
            if x.is_integer(): return str(int(x))
        except Exception: pass
        return str(v)
    x=_float(v)
    if x is None: return str(v)
    if kind=="percent": return f"{x:,.2f}%"
    if kind=="integer": return f"{x:,.0f}"
    return f"{x:,.2f}"


def _identifier_column(name: str) -> bool:
    nn=_norm(name)
    if nn in {"cliente","customer","producto","product","vendedor","seller"}:
        return True
    n=" "+nn+" "
    return any(k in n for k in (" id ","customer id","cliente id"," codigo "," código "," folio "," invoice "," factura "," sku "," stockcode "," stock code "))


def _display_df(df: pd.DataFrame) -> pd.DataFrame:
    out=df.copy()
    for c in out.columns:
        if _identifier_column(str(c)): out[c]=out[c].map(lambda v:_fmt(v,"id"))
    return out


def _cancel_mask(work: pd.DataFrame, roles: Dict[str,Optional[str]]) -> pd.Series:
    mask=pd.Series(False,index=work.index)
    if "_cantidad" in work.columns: mask=mask|(pd.to_numeric(work["_cantidad"],errors="coerce")<0)
    inv=roles.get("invoice")
    if inv and inv in work.columns: mask=mask|work[inv].astype(str).str.upper().str.startswith("C",na=False)
    if "_ventas" in work.columns: mask=mask|(pd.to_numeric(work["_ventas"],errors="coerce")<0)
    return mask.fillna(False)


def enrich_sections(work: pd.DataFrame, roles: Dict[str,Optional[str]], sections: Dict[str,pd.DataFrame], profile: Dict[str,Any]) -> Dict[str,pd.DataFrame]:
    out=dict(sections)

    # V7: el perfil y la calidad pertenecen al archivo completo. Nunca deben heredar
    # un subconjunto filtrado por una pregunta especifica.
    full_profile = profile.get("perfil_columnas")
    if isinstance(full_profile, list) and full_profile:
        out["Perfil_Columnas"] = pd.DataFrame(full_profile)

    # IDs/folios/codigos son dimensiones, nunca metricas.
    prof = out.get("Perfil_Columnas")
    if prof is not None and not prof.empty and "Columna" in prof.columns:
        prof = prof.copy()
        for idx, row in prof.iterrows():
            if _identifier_column(str(row.get("Columna", ""))):
                prof.at[idx, "Tipo_detectado"] = "identificador"
                for c in ("Min", "Max", "Promedio", "Mediana", "Suma"):
                    if c in prof.columns:
                        prof.at[idx, c] = None
        out["Perfil_Columnas"] = prof

    # Comparativo anual con cobertura real. Tener datos en los 12 meses no significa
    # que el ultimo ano este cerrado (p.ej. datos hasta el 09-dic).
    if "_anio" in work.columns and "_ventas" in work.columns and "_fecha" in work.columns:
        all_dates = pd.to_datetime(work["_fecha"], errors="coerce")
        valid_dates = all_dates.dropna()
        global_min = valid_dates.min() if len(valid_dates) else None
        global_max = valid_dates.max() if len(valid_dates) else None
        rows=[]
        for year,g in work.loc[work["_anio"].notna()].groupby("_anio",dropna=True):
            dates=pd.to_datetime(g["_fecha"],errors="coerce").dropna()
            if dates.empty:
                continue
            year_i=int(year); months=int(dates.dt.month.nunique()); dmin=dates.min(); dmax=dates.max()
            first_boundary = bool(global_min is not None and year_i == int(global_min.year) and dmin.month > 1)
            last_boundary = bool(global_max is not None and year_i == int(global_max.year) and (dmax.month < 12 or (dmax.month == 12 and dmax.day < 20)))
            complete = months == 12 and not first_boundary and not last_boundary
            coverage = "Completo" if complete else f"Parcial ({dmin.strftime('%Y-%m-%d')} a {dmax.strftime('%Y-%m-%d')}; {months}/12 meses)"
            row={
                "Año":year_i,
                "Ventas":float(pd.to_numeric(g["_ventas"],errors="coerce").sum(skipna=True)),
                "Meses_con_datos":months,
                "Cobertura":coverage,
                "Desde":dmin.date().isoformat(),
                "Hasta":dmax.date().isoformat(),
            }
            if "_cantidad" in g.columns: row["Unidades"]=float(pd.to_numeric(g["_cantidad"],errors="coerce").sum(skipna=True))
            inv=roles.get("invoice")
            if inv and inv in g.columns: row["Operaciones"]=int(g[inv].nunique(dropna=True))
            rows.append(row)
        annual=pd.DataFrame(rows).sort_values("Año").reset_index(drop=True) if rows else pd.DataFrame()
        if not annual.empty:
            annual["Variación_%"] = None
            annual["Variación_comparable_%"] = None
            annual["Periodo_comparable"] = None
            for i in range(1,len(annual)):
                prev=annual.iloc[i-1]; cur=annual.iloc[i]
                if prev["Cobertura"] == "Completo" and cur["Cobertura"] == "Completo":
                    pv=_float(prev["Ventas"]); cv=_float(cur["Ventas"])
                    if pv:
                        annual.at[i,"Variación_%"]=(cv/pv-1.0)*100.0
            # Para el ultimo ano parcial calcula un YoY a la misma fecha del ano previo.
            if global_max is not None and len(annual)>=2:
                cy=int(global_max.year); py=cy-1
                cur_idx=annual.index[annual["Año"].eq(cy)].tolist()
                prev_idx=annual.index[annual["Año"].eq(py)].tolist()
                if cur_idx and prev_idx and annual.at[cur_idx[0],"Cobertura"] != "Completo":
                    # Compara dias completos, no la hora exacta de la ultima factura.
                    # Si el archivo termina 2011-12-09 12:50, el comparable correcto
                    # es todo el 09-dic de ambos anos.
                    cutoff_cur=(pd.Timestamp(global_max).normalize()+pd.Timedelta(days=1)-pd.Timedelta(nanoseconds=1))
                    try:
                        cutoff_prev=(cutoff_cur.replace(year=py))
                    except ValueError:
                        cutoff_prev=(cutoff_cur.replace(year=py,day=28))
                    cur_mask=(all_dates.dt.year.eq(cy)) & (all_dates<=cutoff_cur)
                    prev_mask=(all_dates.dt.year.eq(py)) & (all_dates<=cutoff_prev)
                    cur_sales=float(pd.to_numeric(work.loc[cur_mask,"_ventas"],errors="coerce").sum(skipna=True))
                    prev_sales=float(pd.to_numeric(work.loc[prev_mask,"_ventas"],errors="coerce").sum(skipna=True))
                    if prev_sales:
                        idx=cur_idx[0]
                        annual.at[idx,"Variación_comparable_%"]=(cur_sales/prev_sales-1.0)*100.0
                        annual.at[idx,"Periodo_comparable"]=f"01-01 a {cutoff_cur.strftime('%m-%d')} vs {py}"
            out["Comparativo_Anual"]=annual

    # Calidad calculada sobre las columnas originales completas.
    quality=profile.get("calidad_archivo") if isinstance(profile.get("calidad_archivo"),dict) else {}
    filas=int(quality.get("filas") or profile.get("filas") or len(work))
    dup=int(quality.get("filas_duplicadas") or 0)
    null_pct=float(quality.get("celdas_nulas_pct") or 0.0)
    q=[
        ("Filas analizadas",filas,"Volumen procesado"),
        ("Filas idénticas detectadas",dup,"Validar antes de eliminar; pueden ser transacciones legítimas"),
        ("Filas idénticas %",float(quality.get("filas_duplicadas_pct") or ((dup/filas*100.0) if filas else 0.0)),"Indicador de revisión de calidad"),
        ("Celdas nulas %",null_pct,"Porcentaje global de valores faltantes"),
    ]
    cust=roles.get("customer")
    if cust and cust in work.columns:
        q.append((f"{cust} nulo %",float(work[cust].isna().mean()*100.0),"Impacta análisis y segmentación por cliente"))
    out["Calidad_Datos"]=pd.DataFrame(q,columns=["Indicador","Valor","Interpretación"])

    if "_ventas" in work.columns:
        net=float(pd.to_numeric(work["_ventas"],errors="coerce").sum(skipna=True)); conc=[]
        for sec,label in (("Top_Productos","Top 5 productos"),("Top_Clientes","Top 5 clientes"),("Top_Paises","Top 5 países")):
            df=out.get(sec)
            if df is not None and not df.empty and len(df.columns)>=2 and net:
                val=pd.to_numeric(df.iloc[:,1],errors="coerce").head(5).sum(skipna=True)
                conc.append({"Dimensión":label,"Ventas_Top5":float(val),"Participación_%":float(val/net*100.0)})
        if conc: out["Concentracion"]=pd.DataFrame(conc)
        mask=_cancel_mask(work,roles); prod=roles.get("product")
        if mask.any() and prod and prod in work.columns:
            tmp=work.loc[mask & work[prod].notna(),[prod,"_ventas"]].copy()
            if not tmp.empty:
                tmp["Impacto"]=pd.to_numeric(tmp["_ventas"],errors="coerce").abs()
                ret=tmp.groupby(prod,dropna=True)["Impacto"].sum(min_count=1).reset_index().sort_values("Impacto",ascending=False).head(15)
                out["Top_Devoluciones"]=ret.rename(columns={prod:"Producto","Impacto":"Importe_devuelto_cancelado"}).reset_index(drop=True)
    return out

def executive_insights(profile: Dict[str,Any], sections: Dict[str,pd.DataFrame], notes: List[str], domain: str) -> List[str]:
    out=[]
    if domain=="comercial":
        k=_metric_dict(sections,"KPIs_Comerciales"); sales=_float(k.get("Ventas netas")); ops=_float(k.get("Operaciones totales")); ticket=_float(k.get("Ticket promedio neto")); pos=_float(k.get("Ventas positivas")); neg=_float(k.get("Importe devoluciones/cancelaciones"))
        if sales is not None:
            s=f"Ventas netas de {_compact(sales)}"
            if ops is not None: s+=f" en {ops:,.0f} operaciones"
            if ticket is not None: s+=f", con ticket promedio de {ticket:,.2f}"
            out.append(s+".")
        canc=_metric_dict(sections,"Cancelaciones"); cancel_net=_float(canc.get("Importe neto asociado"))
        impact=abs(cancel_net) if cancel_net is not None else (abs(neg) if neg is not None else None)
        if impact is not None:
            ratio=impact/pos*100.0 if pos else None; s=f"Impacto neto de cancelaciones/devoluciones por {_compact(impact)}"
            if ratio is not None: s+=f", equivalente al {ratio:.2f}% de las ventas positivas"
            out.append(s+".")
        country=sections.get("Top_Paises")
        if country is not None and not country.empty and sales:
            top=country.iloc[0]; share=(_float(top.iloc[1]) or 0.0)/sales*100.0
            out.append(f"{_fmt(top.iloc[0],'id')} concentra {share:.2f}% de las ventas netas; existe una concentración geográfica relevante.")
        trend=sections.get("Tendencia_Mensual")
        if trend is not None and not trend.empty and "Ventas" in trend.columns:
            closed=trend.copy(); maxp=profile.get("periodo",{}).get("hasta") if isinstance(profile.get("periodo"),dict) else None; partial=False
            try: partial=pd.Timestamp(maxp).day<25
            except Exception: pass
            if partial and len(closed)>1:
                lm=str(closed.iloc[-1]["Mes"]); closed=closed.iloc[:-1]; out.append(f"El último mes ({lm}) es parcial según la fecha máxima del archivo; no debe compararse como un mes cerrado.")
            if not closed.empty:
                mx=closed.loc[pd.to_numeric(closed["Ventas"],errors="coerce").idxmax()]; out.append(f"El mejor mes observado fue {mx['Mes']} con {_compact(mx['Ventas'])} en ventas.")
        annual=sections.get("Comparativo_Anual")
        if annual is not None and len(annual)>=2:
            complete=annual[annual["Cobertura"].eq("Completo")] if "Cobertura" in annual.columns else annual
            if len(complete)>=2:
                a,b=complete.iloc[-2],complete.iloc[-1]; ch=_float(b.get("Variación_%"))
                if ch is not None: out.append(f"Entre {int(a['Año'])} y {int(b['Año'])}, ambos periodos cerrados, las ventas variaron {ch:+.2f}%.")
            last=annual.iloc[-1]
            comp=_float(last.get("Variación_comparable_%")) if "Variación_comparable_%" in annual.columns else None
            if comp is not None:
                period=str(last.get("Periodo_comparable") or "el mismo corte del año anterior")
                out.append(f"El periodo parcial de {int(last['Año'])} comparado al mismo corte ({period}) presenta una variación de {comp:+.2f}%.")
    quality=sections.get("Calidad_Datos")
    if quality is not None and not quality.empty:
        for _,r in quality.iterrows():
            label=str(r["Indicador"]); val=_float(r["Valor"])
            if "nulo %" in label.lower() and val is not None and val>=5:
                out.append(f"Calidad de datos: {label} = {val:.2f}%; esta ausencia debe considerarse al interpretar segmentaciones."); break
        d=quality.loc[quality["Indicador"].eq("Filas idénticas %")]
        if not d.empty:
            dv=_float(d.iloc[0]["Valor"])
            if dv is not None and dv>=1: out.append(f"Se detectó {dv:.2f}% de filas idénticas; deben validarse antes de tratarlas como duplicados eliminables.")
    if not out:
        g=_metric_dict(sections,"KPIs_Generales"); rows=_float(g.get("Filas")) or profile.get("filas",0); nulls=_float(g.get("Celdas nulas %")); out.append(f"Se analizaron {int(rows):,} filas y {len(profile.get('columnas',[]))} columnas.")
        if nulls is not None: out.append(f"El porcentaje global de celdas nulas es {nulls:.2f}%.")
    if any("no se detecto costo" in _norm(n) for n in notes): out.append("El archivo no contiene un costo utilizable; utilidad y margen real no se presentan para evitar estimaciones no respaldadas.")
    return out[:8]


def _kpi_cards(profile: Dict[str,Any], sections: Dict[str,pd.DataFrame], domain: str) -> List[Tuple[str,str,str,str]]:
    if domain=="comercial":
        k=_metric_dict(sections,"KPIs_Comerciales")
        sales=_float(k.get("Ventas netas")); ops=_float(k.get("Operaciones totales")); ticket=_float(k.get("Ticket promedio neto")); pos=_float(k.get("Ventas positivas"))
        if sales is None: sales=_float(profile.get("ventas_totales"))
        if ops is None: ops=_float(profile.get("operaciones"))
        canc=_metric_dict(sections,"Cancelaciones"); cancel_net=_float(canc.get("Importe neto asociado")); neg=_float(k.get("Importe devoluciones/cancelaciones")); impact=abs(cancel_net) if cancel_net is not None else (abs(neg) if neg is not None else None); cp=impact/pos*100.0 if pos and impact is not None else None
        cancel_sub=(f"{_compact(impact)} impacto neto" if impact is not None else "Sin dato calculable")
        return [("VENTAS NETAS",_compact(sales),"Importe acumulado",BLUE),("OPERACIONES",_fmt(ops,"integer"),"Facturas/operaciones únicas",TEAL),("TICKET PROMEDIO",_fmt(ticket),"Venta neta por operación válida",GREEN),("DEVOLUCIONES",_fmt(cp,"percent") if cp is not None else "N/D",cancel_sub,ORANGE)]
    g=_metric_dict(sections,"KPIs_Generales")
    return [("FILAS",_compact(g.get("Filas",profile.get("filas",0)),0),"Registros analizados",BLUE),("COLUMNAS",_fmt(g.get("Columnas",len(profile.get("columnas",[]))),"integer"),"Variables detectadas",TEAL),("CELDAS NULAS",_fmt(g.get("Celdas nulas %",0),"percent"),"Calidad global",ORANGE),("FILAS IDÉNTICAS",_fmt(g.get("Filas duplicadas",0),"integer"),"Requieren validación",PURPLE)]


def _safe_sheet(name: str) -> str: return re.sub(r"[\\/*?:\[\]]","_",name)[:31] or "Resultado"


def _sheet_mapping(sections: Dict[str,pd.DataFrame], domain: str) -> List[Tuple[str,str]]:
    if domain=="comercial": pref=[("Comparativo_Anual","Comparativo_Anual"),("Tendencia_Mensual","Ventas_Mensuales"),("Top_Productos","Productos"),("Top_Clientes","Clientes"),("Top_Paises","Paises"),("Cancelaciones","Cancelaciones"),("Top_Devoluciones","Devoluciones_Producto"),("Concentracion","Concentracion"),("Calidad_Datos","Calidad_Datos"),("Perfil_Columnas","Perfil_Columnas")]
    else: pref=[("Resultado","Resultado"),("Tendencia_Generica","Tendencia"),("Calidad_Datos","Calidad_Datos"),("Perfil_Columnas","Perfil_Columnas"),("Estadisticos_Numericos","Estadisticos")]+[(k,k) for k in sections if k.startswith("Top_")]
    seen=set(); out=[]
    for k,n in pref:
        if k in sections and k not in seen: out.append((k,_safe_sheet(n))); seen.add(k)
    if domain != "comercial":
        for k in sections:
            if k not in seen and k not in {"KPIs_Generales","KPIs_Comerciales","Correlaciones","Tendencia_Generica"}: out.append((k,_safe_sheet(k))); seen.add(k)
    elif "Resultado" in sections and "Resultado" not in seen:
        out.append(("Resultado", "Resultado"))
    return out


def _column_kind(name: str, series: pd.Series) -> str:
    n=_norm(name)
    if n in {"año","ano","year"}: return "id"
    if _identifier_column(name): return "id"
    if any(k in n for k in ("variacion","variación","margen","participacion","participación","porcentaje","%")): return "percent"
    if any(k in n for k in ("ventas","importe","monto","precio","costo","utilidad","ticket","revenue","sales","impacto")): return "amount"
    if any(k in n for k in ("unidades","operaciones","registros","filas","conteo","cantidad","meses con datos","meses_con_datos")): return "integer"
    if pd.api.types.is_datetime64_any_dtype(series): return "date"
    if pd.api.types.is_numeric_dtype(series): return "number"
    return "text"


def _write_table_sheet(writer, sheet_name: str, df: pd.DataFrame, title: str, tab: str) -> Dict[str,Any]:
    wb=writer.book; ws=wb.add_worksheet(sheet_name); writer.sheets[sheet_name]=ws; ws.hide_gridlines(2); ws.set_zoom(90); ws.set_tab_color(tab); ws.set_row(0,28)
    ws.write(0,0,title,wb.add_format({"bold":True,"font_size":16,"font_color":NAVY})); ws.write(1,0,"Datos calculados automáticamente a partir del archivo fuente. Use filtros para explorar el detalle.",wb.add_format({"font_size":9,"font_color":MID}))
    show=_display_df(df); sr=3; show.to_excel(writer,sheet_name=sheet_name,startrow=sr,index=False)
    if len(show.columns)==0: return {"sheet":sheet_name,"startrow":sr,"rows":0,"cols":0,"df":show}
    hf=wb.add_format({"bold":True,"font_color":WHITE,"bg_color":NAVY,"align":"left","valign":"vcenter"}); tf=wb.add_format({"valign":"top"}); nf=wb.add_format({"num_format":"#,##0.00;[Red]-#,##0.00"}); inf=wb.add_format({"num_format":"#,##0;[Red]-#,##0"}); pf=wb.add_format({"num_format":"0.00\"%\";[Red]-0.00\"%\""}); dfmt=wb.add_format({"num_format":"yyyy-mm-dd"})
    for j,c in enumerate(show.columns):
        ws.write(sr,j,str(c),hf); kind=_column_kind(str(c),show[c])
        if kind=="id": width,fmt=min(22,max(12,len(str(c))+2)),tf
        elif kind=="percent": width,fmt=14,pf
        elif kind=="amount": width,fmt=18,nf
        elif kind=="integer": width,fmt=16,inf
        elif kind=="date": width,fmt=14,dfmt
        elif kind=="number": width,fmt=16,nf
        else:
            sample=max([len(str(c))]+[len(str(x)) for x in show[c].dropna().astype(str).head(100)]); width,fmt=min(38,max(14,sample+2)),tf
        ws.set_column(j,j,width,fmt)
    er=sr+len(show)
    if len(show):
        name=re.sub(r"[^A-Za-z0-9]","",sheet_name)[:20]+"Tbl"; ws.add_table(sr,0,er,len(show.columns)-1,{"name":name,"style":"Table Style Medium 2","columns":[{"header":str(c)} for c in show.columns]}); ws.freeze_panes(sr+1,0)
        green=wb.add_format({"font_color":GREEN,"bg_color":PALE_GREEN}); red=wb.add_format({"font_color":RED,"bg_color":PALE_RED})
        for j,c in enumerate(show.columns):
            n=_norm(c)
            if any(k in n for k in ("variacion","variación","margen","participacion","participación","%")):
                ws.conditional_format(sr+1,j,er,j,{"type":"cell","criteria":">","value":0,"format":green}); ws.conditional_format(sr+1,j,er,j,{"type":"cell","criteria":"<","value":0,"format":red})
            elif _column_kind(str(c),show[c])=="amount" and len(show)<=100: ws.conditional_format(sr+1,j,er,j,{"type":"data_bar","bar_color":BLUE,"bar_solid":True})
    return {"sheet":sheet_name,"startrow":sr,"rows":len(show),"cols":len(show.columns),"df":show}


def excel_report_professional(path,prompt: str,profile: Dict[str,Any],plan: Dict[str,Any],sections: Dict[str,pd.DataFrame],notes: List[str],narrative: str,source_preview: pd.DataFrame,work: pd.DataFrame,roles: Dict[str,Optional[str]],domain: str)->None:
    insights=executive_insights(profile,sections,notes,domain)
    manifest=profile.get("deliverable_manifest") if isinstance(profile.get("deliverable_manifest"),dict) else {}
    with pd.ExcelWriter(path,engine="xlsxwriter") as writer:
        wb=writer.book; wb.set_properties({"title":domain_title(domain),"subject":"Reporte ejecutivo generado por IA Empresarial Local","author":"IA Empresarial Local"})
        ws=wb.add_worksheet("Dashboard"); writer.sheets["Dashboard"]=ws; ws.hide_gridlines(2); ws.set_zoom(90); ws.set_tab_color(BLUE); ws.set_column("A:L",13); ws.set_row(0,30); ws.set_row(1,30)
        titlef=wb.add_format({"bold":True,"font_size":22,"font_color":WHITE,"bg_color":NAVY,"align":"left","valign":"vcenter"}); secf=wb.add_format({"bold":True,"font_size":13,"font_color":NAVY,"bottom":2,"bottom_color":BLUE}); bullet=wb.add_format({"font_size":10,"font_color":"#343A3F","text_wrap":True,"valign":"top"}); note=wb.add_format({"font_size":9,"font_color":"#525252","bg_color":LIGHT,"text_wrap":True,"valign":"top"})
        ws.merge_range("A1:L2",domain_title(domain),titlef); period=profile.get("periodo") if isinstance(profile.get("periodo"),dict) else {}; pt=f" | Periodo: {str(period.get('desde',''))[:10]} a {str(period.get('hasta',''))[:10]}" if period else ""; ws.merge_range("A3:L3",f"Archivo: {profile.get('archivo','')} | Filas: {int(profile.get('filas',0)):,}{pt}",wb.add_format({"font_size":9,"font_color":MID}))
        cards=_kpi_cards(profile,sections,domain); ranges=[("A5:C5","A6:C7"),("D5:F5","D6:F7"),("G5:I5","G6:I7"),("J5:L5","J6:L7")]
        for (label,value,caption,color),(rl,rv) in zip(cards,ranges):
            ws.merge_range(rl,label,wb.add_format({"bold":True,"font_size":8,"font_color":WHITE,"bg_color":color,"align":"left","valign":"vcenter"})); ws.merge_range(rv,value,wb.add_format({"bold":True,"font_size":18,"font_color":NAVY,"bg_color":WHITE,"border":1,"border_color":BORDER,"align":"center","valign":"vcenter"}))
        for col,card in zip((0,3,6,9),cards): ws.merge_range(8,col,8,col+2,card[2],wb.add_format({"font_size":8,"font_color":MID,"align":"center"}))
        ws.merge_range("A10:F10","Hallazgos clave",secf); r=10
        for ins in insights[:7]: ws.merge_range(r,0,r,5,"• "+ins,bullet); ws.set_row(r,30); r+=1
        meta={}; tabs=[BLUE,TEAL,GREEN,ORANGE,PURPLE,"#8A3FFC"]
        for i,(key,sn) in enumerate(_sheet_mapping(sections,domain)): meta[key]=_write_table_sheet(writer,sn,sections[key],key.replace("_"," "),tabs[i%len(tabs)])
        roles_df=pd.DataFrame([{"Rol semántico":k,"Columna detectada":v or ""} for k,v in profile.get("roles_detectados",{}).items()]); _write_table_sheet(writer,"Diccionario_Datos",roles_df,"Diccionario y mapeo semántico",MID)
        trace=pd.DataFrame([{"Campo":"Solicitud","Valor":prompt},{"Campo":"Plan","Valor":str(plan)},{"Campo":"Cálculos derivados","Valor":str(profile.get("calculos_derivados",{}))},{"Campo":"Motor Excel","Valor":str(profile.get("motor_excel",""))}]); _write_table_sheet(writer,"Trazabilidad",trace,"Trazabilidad técnica",MID); _write_table_sheet(writer,"Muestra_Datos",source_preview.head(1000),"Muestra del archivo fuente (máx. 1,000 filas)",MID); writer.sheets["Trazabilidad"].hide(); writer.sheets["Muestra_Datos"].hide(); writer.sheets["Diccionario_Datos"].hide()
        if manifest:
            _write_table_sheet(writer,"Gobernanza",pd.DataFrame(deliverable_manifest_summary_rows(manifest)),"Manifiesto gobernado del entregable",TEAL)
            writer.sheets["Gobernanza"].set_column("A:A",28)
            writer.sheets["Gobernanza"].set_column("B:B",72)
            _write_table_sheet(writer,"Capacidades",pd.DataFrame(deliverable_manifest_component_rows(manifest)),"Capacidades autorizadas y bloqueadas",ORANGE)
        if domain=="comercial" and "Tendencia_Mensual" in meta:
            m=meta["Tendencia_Mensual"]; d=m["df"]
            if not d.empty and "Mes" in d.columns and "Ventas" in d.columns:
                ci=d.columns.get_loc("Mes"); vi=d.columns.get_loc("Ventas"); ch=wb.add_chart({"type":"line"}); ch.add_series({"name":"Ventas","categories":[m["sheet"],m["startrow"]+1,ci,m["startrow"]+len(d),ci],"values":[m["sheet"],m["startrow"]+1,vi,m["startrow"]+len(d),vi],"line":{"color":BLUE,"width":2.25},"marker":{"type":"circle","size":4,"border":{"color":BLUE},"fill":{"color":WHITE}}}); ch.set_title({"name":"Evolución mensual de ventas"}); ch.set_legend({"none":True}); ch.set_chartarea({"border":{"none":True}}); ch.set_plotarea({"border":{"color":BORDER},"fill":{"color":WHITE}}); ymax=float(pd.to_numeric(d["Ventas"],errors="coerce").abs().max() or 0); yfmt="#,##0.00" if ymax<1000 else ("#,##0.0,\" K\"" if ymax<1000000 else "#,##0.0,,\" M\""); ch.set_y_axis({"num_format":yfmt,"major_gridlines":{"visible":True,"line":{"color":"#E0E0E0"}}}); ch.set_x_axis({"interval_unit":2}); ws.insert_chart("G10",ch,{"x_scale":1.15,"y_scale":1.05})
        elif "Tendencia_Generica" in meta:
            m=meta["Tendencia_Generica"]; d=m["df"]
            if not d.empty and len(d.columns)>=2:
                ch=wb.add_chart({"type":"line"}); ch.add_series({"name":str(d.columns[1]),"categories":[m["sheet"],m["startrow"]+1,0,m["startrow"]+len(d),0],"values":[m["sheet"],m["startrow"]+1,1,m["startrow"]+len(d),1],"line":{"color":BLUE,"width":2}}); ch.set_title({"name":"Tendencia"}); ch.set_legend({"none":True}); ws.insert_chart("G10",ch,{"x_scale":1.15,"y_scale":1.05})
        ws.merge_range("A24:F24","Principales productos / categorías",secf); ws.merge_range("G24:L24","Distribución geográfica / categorías",secf)
        def bar(key,cell,title,color):
            m=meta.get(key)
            if not m or m["rows"]==0 or m["cols"]<2:return
            d=m["df"].head(10); ch=wb.add_chart({"type":"bar"}); ch.add_series({"name":title,"categories":[m["sheet"],m["startrow"]+1,0,m["startrow"]+len(d),0],"values":[m["sheet"],m["startrow"]+1,1,m["startrow"]+len(d),1],"fill":{"color":color},"border":{"none":True}}); ch.set_title({"name":title}); ch.set_legend({"none":True}); ch.set_chartarea({"border":{"none":True}}); ch.set_plotarea({"border":{"none":True}}); ch.set_x_axis({"major_gridlines":{"visible":True,"line":{"color":"#E0E0E0"}},"num_format":"#,##0"}); ch.set_y_axis({"reverse":True}); ws.insert_chart(cell,ch,{"x_scale":1.0,"y_scale":1.05})
        if domain=="comercial": bar("Top_Productos","A25","Top 10 productos por ventas",BLUE); bar("Top_Paises","G25","Top 10 países por ventas",TEAL)
        else:
            tops=[k for k in meta if k.startswith("Top_")]
            if tops: bar(tops[0],"A25",tops[0].replace("_"," "),BLUE)
            if len(tops)>1: bar(tops[1],"G25",tops[1].replace("_"," "),TEAL)
        ws.merge_range("A43:L43","Notas y limitaciones",secf); un=[]
        for n in notes:
            n=str(n).strip()
            if n and n not in un: un.append(n)
        if not un: un=["No se reportaron limitaciones adicionales por el motor de análisis."]
        for i,n in enumerate(un[:4],start=44): ws.merge_range(i-1,0,i-1,11,"• "+n,note); ws.set_row(i-1,24)
        ws.merge_range("A49:L49","Metodología",secf); ws.merge_range("A50:L52","Los cálculos se ejecutan localmente con Python sobre el archivo completo. La IA local recibe únicamente resultados agregados para redactar la interpretación. Los identificadores no se tratan como métricas numéricas y no se calculan costos, utilidad o márgenes cuando el archivo no contiene información suficiente.",note); ws.freeze_panes(4,0); ws.activate(); ws.set_first_sheet()


def _chart_image(kind: str,df: pd.DataFrame,title: str,x_col: str,y_col: str,color: str=BLUE,max_rows: int=15)->Optional[BytesIO]:
    if df is None or df.empty or x_col not in df.columns or y_col not in df.columns:return None
    show=_display_df(df[[x_col,y_col]].copy()).head(max_rows); y=pd.to_numeric(df[y_col],errors="coerce").head(max_rows)
    if not y.notna().any(): return None
    fig,ax=plt.subplots(figsize=(8.8,3.2))
    if kind=="line": ax.plot(show[x_col].astype(str),y,marker="o",linewidth=2.2,color=color); ax.tick_params(axis="x",labelrotation=45,labelsize=7)
    else: ax.barh(show[x_col].astype(str).tolist()[::-1],y.tolist()[::-1],color=color); ax.tick_params(axis="y",labelsize=7)
    ax.set_title(title,loc="left",fontsize=11,fontweight="bold",color=NAVY); ax.spines[["top","right","left"]].set_visible(False); ax.grid(axis="y" if kind=="line" else "x",alpha=.18); ax.tick_params(colors="#525252",labelsize=7); ax.set_facecolor("white"); fig.patch.set_facecolor("white"); fig.tight_layout(); b=BytesIO(); fig.savefig(b,format="png",dpi=160,bbox_inches="tight"); plt.close(fig); b.seek(0); return b


def _pdf_table(df: pd.DataFrame, styles, max_rows: int=10)->Table:
    show=_display_df(df.head(max_rows).copy()); body=[[Paragraph(f"<b>{str(c).replace(chr(95), chr(32))}</b>",styles["TableHead"]) for c in show.columns]]
    for _,r in show.iterrows():
        row=[]
        for c,v in r.items():
            kind=_column_kind(str(c),show[c]); fmt_kind="id" if kind=="id" else "percent" if kind=="percent" else "integer" if kind=="integer" else "number"; row.append(Paragraph(_fmt(v,fmt_kind),styles["TableCell"]))
        body.append(row)
    widths=[25.2*cm/max(1,len(show.columns))]*max(1,len(show.columns)); t=Table(body,colWidths=widths,repeatRows=1,hAlign="LEFT"); t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor(NAVY)),("TEXTCOLOR",(0,0),(-1,0),colors.white),("GRID",(0,0),(-1,-1),.35,colors.HexColor(BORDER)),("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,colors.HexColor("#FAFAFA")]),("VALIGN",(0,0),(-1,-1),"MIDDLE"),("LEFTPADDING",(0,0),(-1,-1),5),("RIGHTPADDING",(0,0),(-1,-1),5),("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4)])); return t


def pdf_report_professional(path,prompt: str,profile: Dict[str,Any],sections: Dict[str,pd.DataFrame],notes: List[str],narrative: str,domain: str)->None:
    insights=executive_insights(profile,sections,notes,domain); cards=_kpi_cards(profile,sections,domain); doc=SimpleDocTemplate(str(path),pagesize=landscape(A4),rightMargin=1.1*cm,leftMargin=1.1*cm,topMargin=1.5*cm,bottomMargin=1.25*cm,title=domain_title(domain),author="IA Empresarial Local")
    manifest=profile.get("deliverable_manifest") if isinstance(profile.get("deliverable_manifest"),dict) else {}
    st=getSampleStyleSheet(); st.add(ParagraphStyle(name="ExecTitle",parent=st["Title"],fontName="Helvetica-Bold",fontSize=21,leading=24,textColor=colors.HexColor(NAVY),alignment=TA_LEFT,spaceAfter=4)); st.add(ParagraphStyle(name="ExecSub",parent=st["BodyText"],fontSize=8.5,leading=11,textColor=colors.HexColor(MID),spaceAfter=5)); st.add(ParagraphStyle(name="Sec",parent=st["Heading2"],fontName="Helvetica-Bold",fontSize=13,leading=16,textColor=colors.HexColor(NAVY),spaceBefore=6,spaceAfter=7)); st.add(ParagraphStyle(name="Insight",parent=st["BodyText"],fontSize=9.2,leading=13,textColor=colors.HexColor("#343A3F"),leftIndent=8,firstLineIndent=-6,spaceAfter=4)); st.add(ParagraphStyle(name="Small",parent=st["BodyText"],fontSize=7.5,leading=10,textColor=colors.HexColor(MID))); st.add(ParagraphStyle(name="TableHead",parent=st["BodyText"],fontSize=7,leading=8,textColor=colors.white)); st.add(ParagraphStyle(name="TableCell",parent=st["BodyText"],fontSize=7,leading=8.5,textColor=colors.HexColor("#343A3F"))); st.add(ParagraphStyle(name="Card",parent=st["BodyText"],fontSize=9,leading=12,alignment=TA_CENTER,textColor=colors.HexColor(NAVY)))
    def page(can,doc_):
        can.saveState(); w,h=landscape(A4); can.setFillColor(colors.HexColor(NAVY)); can.rect(0,h-.55*cm,w,.55*cm,stroke=0,fill=1); can.setFillColor(colors.HexColor(MID)); can.setFont("Helvetica",7); can.drawString(1.1*cm,.55*cm,"IA Empresarial Local | Reporte generado localmente"); can.drawRightString(w-1.1*cm,.55*cm,f"Página {doc_.page}"); can.restoreState()
    story=[Paragraph(domain_title(domain),st["ExecTitle"])]; period=profile.get("periodo") if isinstance(profile.get("periodo"),dict) else {}; meta=f"Archivo: <b>{profile.get('archivo','')}</b> &nbsp; | &nbsp; Filas: <b>{int(profile.get('filas',0)):,}</b>"; meta+=f" &nbsp; | &nbsp; Periodo: <b>{str(period.get('desde',''))[:10]} a {str(period.get('hasta',''))[:10]}</b>" if period else ""; story+=[Paragraph(meta,st["ExecSub"]),Spacer(1,.1*cm)]
    cells=[Paragraph(f"<font size='7' color='{MID}'><b>{a}</b></font><br/><font size='17' color='{NAVY}'><b>{b}</b></font><br/><font size='6.5' color='{MID}'>{c}</font>",st["Card"]) for a,b,c,_ in cards]; ct=Table([cells],colWidths=[6.1*cm]*4,rowHeights=[2.2*cm]); cs=[("BOX",(0,0),(-1,-1),.5,colors.HexColor(BORDER)),("VALIGN",(0,0),(-1,-1),"MIDDLE")];
    for i,fill in enumerate([PALE_BLUE,"#E5F6FF",PALE_GREEN,PALE_ORANGE]): cs.append(("BACKGROUND",(i,0),(i,0),colors.HexColor(fill)))
    ct.setStyle(TableStyle(cs)); story += [ct,Spacer(1,.25*cm),Paragraph("Hallazgos ejecutivos",st["Sec"])]
    for x in insights: story.append(Paragraph("• "+x,st["Insight"]))
    trend=sections.get("Tendencia_Mensual") if domain=="comercial" else sections.get("Tendencia_Generica")
    if trend is not None and not trend.empty:
        x="Mes" if "Mes" in trend.columns else str(trend.columns[0]); y="Ventas" if "Ventas" in trend.columns else str(trend.columns[1]); b=_chart_image("line",trend,"Evolución temporal",x,y,BLUE,36)
        if b: story.append(Image(b,width=24.5*cm,height=7.2*cm))
    if domain=="comercial":
        story += [PageBreak(),Paragraph("Ventas y evolución",st["ExecTitle"])]
        annual=sections.get("Comparativo_Anual")
        if annual is not None and not annual.empty: story += [Paragraph("Comparativo anual",st["Sec"]),_pdf_table(annual,st,10),Spacer(1,.25*cm)]
        if trend is not None and not trend.empty: story += [Paragraph("Tendencia mensual",st["Sec"]),_pdf_table(trend.tail(18),st,18)]
        story += [PageBreak(),Paragraph("Productos y clientes",st["ExecTitle"])]
        prod=sections.get("Top_Productos"); cli=sections.get("Top_Clientes"); imgs=[]
        if prod is not None and not prod.empty:
            b=_chart_image("bar",prod,"Top productos por ventas",str(prod.columns[0]),str(prod.columns[1]),BLUE,10)
            if b: imgs.append(Image(b,width=12.2*cm,height=6.3*cm))
        if cli is not None and not cli.empty:
            b=_chart_image("bar",cli,"Top clientes por ventas",str(cli.columns[0]),str(cli.columns[1]),PURPLE,10)
            if b: imgs.append(Image(b,width=12.2*cm,height=6.3*cm))
        if imgs:
            while len(imgs)<2: imgs.append(Spacer(1,1))
            story.append(Table([imgs],colWidths=[12.5*cm,12.5*cm]))
        if prod is not None and not prod.empty: story += [Paragraph("Top productos",st["Sec"]),_pdf_table(prod,st,10)]
        if cli is not None and not cli.empty: story += [Paragraph("Top clientes",st["Sec"]),_pdf_table(cli,st,10)]
        story += [PageBreak(),Paragraph("Geografía, devoluciones y concentración",st["ExecTitle"])]
        countries=sections.get("Top_Paises")
        if countries is not None and not countries.empty:
            b=_chart_image("bar",countries,"Ventas por país",str(countries.columns[0]),str(countries.columns[1]),TEAL,10)
            if b: story.append(Image(b,width=24.5*cm,height=6.4*cm))
            story.append(_pdf_table(countries,st,10))
        canc=sections.get("Cancelaciones"); conc=sections.get("Concentracion")
        if canc is not None and not canc.empty: story += [Paragraph("Cancelaciones y devoluciones",st["Sec"]),_pdf_table(canc,st,10)]
        if conc is not None and not conc.empty: story += [Paragraph("Concentración de ventas",st["Sec"]),_pdf_table(conc,st,10)]
    story += [PageBreak(),Paragraph("Calidad de datos y metodología",st["ExecTitle"])]
    quality=sections.get("Calidad_Datos")
    if quality is not None and not quality.empty: story += [Paragraph("Indicadores de calidad",st["Sec"]),_pdf_table(quality,st,15)]
    prof=sections.get("Perfil_Columnas")
    if prof is not None and not prof.empty:
        cols=[c for c in ["Columna","Tipo_detectado","No_nulos","Nulos_%","Valores_unicos","Ejemplos"] if c in prof.columns]; story += [Paragraph("Perfil resumido de columnas",st["Sec"]),_pdf_table(prof[cols],st,25)]
    story += [Spacer(1,.3*cm),Paragraph("Metodología: los cálculos se ejecutan localmente con Python sobre el archivo completo. La IA local se utiliza para interpretar resultados agregados, no para sustituir los cálculos. Los identificadores se tratan como categorías y no como métricas. No se estiman costos, utilidad o márgenes cuando el archivo no contiene datos suficientes.",st["Small"])]
    if notes:
        story.append(Paragraph("Limitaciones",st["Sec"])); un=[]
        for n in notes:
            n=str(n).strip()
            if n and n not in un: un.append(n)
        for n in un[:8]: story.append(Paragraph("• "+n,st["Small"]))
    if manifest:
        story += [PageBreak(),Paragraph("Gobernanza y trazabilidad",st["ExecTitle"]),Paragraph("Este entregable usa la misma autoridad analítica que el dashboard HTML. Las capacidades BLOCKED no se presentan como valores calculados.",st["Small"]),Spacer(1,.2*cm)]
        summary_df=pd.DataFrame(deliverable_manifest_summary_rows(manifest))
        story += [_pdf_table(summary_df,st,20),Spacer(1,.25*cm)]
        components_df=pd.DataFrame(deliverable_manifest_component_rows(manifest))
        blocked=components_df.loc[components_df["Estado"].eq("BLOCKED")] if not components_df.empty else components_df
        story += [Paragraph("Capacidades bloqueadas",st["Sec"])]
        if blocked.empty: story.append(Paragraph("No existen capacidades bloqueadas en esta solicitud.",st["Small"]))
        else: story.append(_pdf_table(blocked[["Componente","Título","Estado","Motivo","Dependencias","Provenance"]],st,20))
    doc.build(story,onFirstPage=page,onLaterPages=page)
