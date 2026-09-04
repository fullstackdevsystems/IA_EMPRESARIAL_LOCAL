"""Tokens visuales reutilizables y offline para entregables empresariales."""
DESIGN_SYSTEM_VERSION = "r10.20a"
_LIGHT={"primary":"#12355b","accent":"#0b8fa3","success":"#16803c","warning":"#a86700","danger":"#b42318","neutral":"#667085","background":"#f5f8fc","surface":"#ffffff","surface_alt":"#eef4f8","border":"#d7e1ea","text_primary":"#172b4d","text_secondary":"#52657a"}
_DARK={**_LIGHT,"background":"#101923","surface":"#172433","surface_alt":"#203246","border":"#39506a","text_primary":"#eef5ff","text_secondary":"#b5c4d6"}
_STATUS={"SUPPORTED":("Supported","success","✓"),"DERIVABLE":("Derivable","warning","◐"),"BLOCKED":("Blocked","danger","!"),"UNRESOLVED":("Unresolved","neutral","?"),"CONFLICT":("Conflict","danger","⚠")}
def get_design_tokens(theme="professional-light"):
    colors=dict(_DARK if theme=="professional-dark" else _LIGHT)
    return {"version":DESIGN_SYSTEM_VERSION,"theme":theme,"colors":colors,"typography":{"title":"clamp(26px,3vw,40px)","section":"18px","metric":"32px","body":"14px","caption":"11px"},"layout":{"max_width":"1600px","spacing":"16px","grid_gap":"16px","card_padding":"18px","radius":"16px","shadow":"0 10px 28px rgba(16,35,58,.10)"},"table":{"header":colors["surface_alt"],"row":colors["surface"],"border":colors["border"],"zebra":colors["background"]},"print":{"page":"#fff","background":"#fff","text":"#111827","spacing":"10px"}}
def get_excel_design_tokens(theme="professional-light"):
    """Presentation values shared by local Excel deliverables.

    These are values rather than workbook-bound formats so every generator can
    create its native format objects without maintaining a second palette.
    """
    colors=get_design_tokens(theme)["colors"]
    return {"version":DESIGN_SYSTEM_VERSION,"theme":theme,"colors":colors,
            "title":{"font_size":22,"background":colors["primary"],"font_color":"#FFFFFF"},
            "subtitle":{"font_size":9,"font_color":colors["text_secondary"]},
            "section":{"font_size":13,"font_color":colors["primary"],"border_color":colors["accent"]},
            "header":{"background":colors["primary"],"font_color":"#FFFFFF"},
            "body":{"font_color":colors["text_primary"],"border_color":colors["border"]},
            "metadata":{"background":colors["surface_alt"],"font_color":colors["text_secondary"]},
            "status":{"SUPPORTED":colors["success"],"DERIVABLE":colors["warning"],"BLOCKED":colors["danger"],"UNRESOLVED":colors["neutral"],"CONFLICT":colors["danger"]},
            "formats":{"integer":"#,##0;[Red]-#,##0","decimal":"#,##0.00;[Red]-#,##0.00","percentage":"0.00%","date":"yyyy-mm-dd","datetime":"yyyy-mm-dd hh:mm","text":"@"},
            "width":{"minimum":10,"maximum":45}}
def get_pdf_design_tokens(theme="professional-light"):
    """Presentation values shared by the local ReportLab deliverable."""
    base=get_design_tokens(theme)
    colors=base["colors"]
    return {"version":DESIGN_SYSTEM_VERSION,"theme":theme,"colors":colors,
            "typography":{"cover":26,"title":20,"section":13,"body":9,"caption":7.5},
            "spacing":{"margin_cm":1.1,"section_cm":0.25},
            "status":{"SUPPORTED":colors["success"],"DERIVABLE":colors["warning"],"BLOCKED":colors["danger"],"UNRESOLVED":colors["neutral"],"CONFLICT":colors["danger"]}}
def status_presentation(status):
    label,tone,symbol=_STATUS.get(str(status or "").upper(),_STATUS["UNRESOLVED"])
    return {"status":str(status or "UNRESOLVED").upper(),"label":label,"class_name":"status-"+tone,"symbol":symbol}
def build_dashboard_css(theme="professional-light"):
    t=get_design_tokens(theme); c=t["colors"]; l=t["layout"]
    return ":root{--ds-primary:%s;--ds-accent:%s;--ds-success:%s;--ds-warning:%s;--ds-danger:%s;--ds-neutral:%s;--ds-bg:%s;--ds-surface:%s;--ds-border:%s;--ds-text:%s;--ds-muted:%s;--ds-radius:%s;--ds-shadow:%s}body{background:var(--ds-bg);color:var(--ds-text)}.main{max-width:%s;margin:auto}.sidebar,.card,.kpi,.table-card,.audit{background:var(--ds-surface);border-color:var(--ds-border);box-shadow:var(--ds-shadow)}h1{font-size:%s}.status-success,.status-warning,.status-danger,.status-neutral{display:inline-flex;gap:5px;align-items:center;border-radius:999px;padding:4px 8px;font-size:11px;font-weight:800}.status-success{color:var(--ds-success)}.status-warning{color:var(--ds-warning)}.status-danger{color:var(--ds-danger)}.status-neutral{color:var(--ds-neutral)}@media print{body,.sidebar,.card,.kpi,.table-card,.audit{background:#fff!important;color:#111827!important;box-shadow:none!important}.sidebar,.toolbar,.actions{display:none!important}.main{padding:0!important;max-width:none!important}}" % (c["primary"],c["accent"],c["success"],c["warning"],c["danger"],c["neutral"],c["background"],c["surface"],c["border"],c["text_primary"],c["text_secondary"],l["radius"],l["shadow"],l["max_width"],t["typography"]["title"])
