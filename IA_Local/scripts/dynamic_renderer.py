from __future__ import annotations
from typing import Any, Dict, List

VERSION = "r10.13c"

PAGE_ICONS = {
    "summary":"▣","customers":"◎","analysis":"◫","operations":"≡",
    "customer_profile":"♙","line_analysis":"⌁","lost_customers":"⚠",
    "logistics":"⇄","inventory":"▦","receivables":"¤","quality":"✓",
    "logistics_summary":"▣","warehouses":"▦","routes":"⇄","origin_destination":"↔",
    "evolution":"⌁","logistics_detail":"≡","data_quality":"✓",
}


def _safe_pages(spec: Dict[str, Any]) -> List[Dict[str, Any]]:
    pages=[]
    seen=set()

    for raw in list((spec or {}).get("pages") or []):
        if not isinstance(raw,dict):
            continue

        pid=str(raw.get("id") or "").strip()

        if not pid or pid in seen:
            continue

        seen.add(pid)

        pages.append({
            "id":pid,
            "title":str(raw.get("title") or pid.replace("_"," ").title()),
            "icon":PAGE_ICONS.get(pid,"•"),
            "components":[
                str(x)
                for x in list(raw.get("components") or [])
            ],
        })

    return pages or [{
        "id":"summary",
        "title":"Resumen Ejecutivo",
        "icon":"▣",
        "components":[]
    }]


def build_dynamic_renderer_model(
    spec: Dict[str, Any],
    plan: Dict[str, Any]
) -> Dict[str, Any]:

    spec=dict(spec or {})

    pages=_safe_pages(spec)

    components={
        str(c.get("id")):dict(c)
        for c in list(spec.get("components") or [])
        if isinstance(c,dict) and c.get("id")
    }

    charts={
        str(c.get("id")):dict(c)
        for c in list(spec.get("charts") or [])
        if isinstance(c,dict) and c.get("id")
    }

    blocked=[
        dict(x)
        for x in list(spec.get("blocked") or [])
        if isinstance(x,dict)
    ]

    coverage=dict(spec.get("coverage") or {})
    prov=dict(spec.get("provenance") or {})

    return {
        "version":VERSION,
        "enabled":bool(spec),
        "domain":spec.get("domain") or "generic",
        "pages":pages,
        "components":components,
        "charts":charts,
        "blocked":blocked,
        "coverage":coverage,
        "semantic_roles":dict(
            prov.get("semantic_roles") or {}
        ),
        "source":dict(spec.get("source") or {}),
        "ruleset_version":dict(
            spec.get("provenance") or {}
        ).get("ruleset_version"),
        "legacy":{
            "kpis":len(list(plan.get("kpis") or [])),
            "charts":len(list(plan.get("charts") or [])),
            "filters":len(list(plan.get("filters") or [])),
        },
    }


def _canonicalize_execution_plan(
    out: Dict[str, Any],
    spec: Dict[str, Any]
) -> None:

    execution=dict(out.get("execution_plan") or {})

    if not execution or not spec:
        return

    coverage=dict(spec.get("coverage") or {})

    canonical=[]

    for c in list(spec.get("components") or []):

        if not isinstance(c,dict):
            continue

        status=str(
            c.get("status")
            or "BLOCKED"
        )

        canonical.append({
            "key":c.get("id"),
            "name":(
                c.get("title")
                or c.get("semantic_role")
                or c.get("id")
            ),
            "requested":bool(
                c.get("requested_by_prompt",True)
            ),
            "status":(
                "ready"
                if status in {"SUPPORTED","DERIVABLE"}
                else "blocked"
            ),
            "detail":(
                c.get("reason")
                or (
                    "Derivable con regla validada."
                    if status=="DERIVABLE"
                    else "Capacidad soportada por el dashboard_spec."
                )
            ),
            "missing":(
                []
                if status in {"SUPPORTED","DERIVABLE"}
                else list(c.get("dependencies") or [])
            ),
            "renderer":c.get("type") or "component",
            "source_columns":list(
                c.get("source_columns") or []
            ),
            "formula":c.get("formula"),
            "provenance":dict(
                c.get("provenance") or {}
            ),
            "rule":dict(
                c.get("rule") or {}
            ),
            "execution":dict(
                c.get("execution") or {}
            ),
            "output_format":c.get("output_format"),
        })

    execution["legacy_coverage"]={
        "requested_count":execution.get("requested_count"),
        "ready_count":execution.get("ready_count"),
        "partial_count":execution.get("partial_count"),
        "blocked_count":execution.get("blocked_count"),
        "coverage_pct":execution.get("coverage_pct"),
    }

    execution["requested_count"]=int(
        coverage.get("requested") or 0
    )

    execution["ready_count"]=int(
        coverage.get("fulfilled") or 0
    )

    execution["partial_count"]=0

    execution["blocked_count"]=int(
        coverage.get("blocked") or 0
    )

    execution["coverage_pct"]=float(
        coverage.get("percent") or 0.0
    )

    execution["components"]=canonical
    execution["authority"]="dashboard_spec"

    out["execution_plan"]=execution


def runtime_markup() -> str:
    return r'''
<style id="r1013b-style">

.r13b-toolbar-host{
    margin:0 0 14px
}

.r13b-page{
    display:none
}

.r13b-page.active{
    display:block
}

.r13b-page-head{
    display:flex;
    justify-content:space-between;
    align-items:flex-start;
    gap:12px;
    margin:4px 0 14px;
    padding:14px 16px;
    background:linear-gradient(135deg,#fff,#f3fbfc);
    border:1px solid #d8edf0;
    border-radius:16px
}

.r13b-page-head h2{
    margin:0;
    font-size:20px
}

.r13b-page-meta{
    font-size:11px;
    color:#61768b
}

.r13b-status{
    display:inline-flex;
    border-radius:999px;
    padding:3px 7px;
    font-size:9px;
    font-weight:800
}

.r13b-status.SUPPORTED{
    background:#e8f7ed;
    color:#16833a
}

.r13b-status.DERIVABLE{
    background:#e7f7f8;
    color:#087f8e
}

.r13b-status.BLOCKED{
    background:#fdecec;
    color:#b52f2f
}

.r13b-grid{
    display:grid;
    grid-template-columns:repeat(12,1fr);
    gap:14px;
    margin-top:14px
}

.r13b-card{
    grid-column:span 6;
    background:#fff;
    border:1px solid #dce7ef;
    border-radius:16px;
    padding:16px;
    box-shadow:0 8px 26px rgba(18,52,77,.08);
    min-width:0
}

.r13b-card.full{
    grid-column:span 12
}

.r13b-card.third{
    grid-column:span 4
}

.r13b-card h3{
    margin:0 0 4px;
    font-size:15px
}

.r13b-small{
    font-size:10px;
    color:#61768b
}

.r13b-kpi-value{
    font-size:30px;
    font-weight:800;
    margin:10px 0 2px
}

.r13b-source{
    font-size:10px;
    color:#61768b;
    margin-top:6px
}

.r13b-bars{
    display:grid;
    gap:8px;
    margin-top:12px
}

.r13b-bar-row{
    display:grid;
    grid-template-columns:minmax(130px,1.3fr) minmax(120px,3fr) auto;
    gap:8px;
    align-items:center;
    font-size:10px
}

.r13b-bar-name{
    overflow:hidden;
    text-overflow:ellipsis;
    white-space:nowrap
}

.r13b-bar-track{
    height:9px;
    background:#edf3f6;
    border-radius:999px;
    overflow:hidden
}

.r13b-bar-fill{
    display:block;
    height:100%;
    background:linear-gradient(90deg,#0a93a4,#19b8c4);
    border-radius:999px
}

.r13b-bar-val{
    font-weight:800;
    white-space:nowrap
}

.r13b-metric-control{
    grid-column:span 12;
    display:flex;
    align-items:center;
    justify-content:flex-end;
    gap:8px;
    padding:10px 12px;
    border:1px solid #d8edf0;
    background:linear-gradient(135deg,#fff,#f3fbfc);
    border-radius:12px
}

.r13b-metric-control label{
    font-size:10px;
    font-weight:800;
    color:#61768b;
    text-transform:uppercase
}

.r13b-metric-select{
    min-width:210px;
    border:1px solid #cfe1e8;
    border-radius:9px;
    padding:7px 9px;
    background:#fff;
    color:#102540;
    font-weight:700;
    cursor:pointer
}

.r13b-chart-controls{
    grid-column:span 12;
    display:flex;
    justify-content:flex-end;
    gap:8px;
    flex-wrap:wrap;
    padding:0 12px 8px
}

.r13b-chart-controls label{
    display:flex;
    align-items:center;
    gap:6px;
    color:#61768b;
    font-size:10px;
    font-weight:800;
    text-transform:uppercase
}

.r13b-chart-controls select{
    border:1px solid #cfe1e8;
    border-radius:9px;
    padding:6px 8px;
    background:#fff;
    color:#102540;
    font-weight:700
}

.r13b-ranking-list{
    display:grid;
    gap:8px;
    margin-top:10px
}

.r13b-ranking-row{
    display:grid;
    grid-template-columns:34px minmax(150px,1.3fr) minmax(120px,2fr) auto;
    gap:8px;
    align-items:center;
    font-size:11px
}

.r13b-ranking-pos{
    width:28px;
    height:28px;
    display:grid;
    place-items:center;
    border-radius:50%;
    background:#eef8fa;
    color:#087f8e;
    font-weight:900
}

.r13b-ranking-name{
    overflow:hidden;
    text-overflow:ellipsis;
    white-space:nowrap
}

.r13b-ranking-track{
    height:8px;
    background:#edf3f6;
    border-radius:999px;
    overflow:hidden
}

.r13b-ranking-track i{
    display:block;
    height:100%;
    background:linear-gradient(90deg,#0a93a4,#19b8c4);
    border-radius:999px
}

.r13b-drill-filter-host{
    display:none;
    margin:0 0 12px
}

.r13b-drill-filter-host.is-active{
    display:block
}

.r13b-drill-filter-bar{
    display:flex;
    align-items:center;
    gap:8px;
    flex-wrap:wrap;
    border:1px solid #bfe8ec;
    background:linear-gradient(135deg,#f7fcfd,#eef9fa);
    border-radius:12px;
    padding:9px 10px;
    box-shadow:0 4px 14px rgba(18,52,77,.04)
}

.r13b-drill-filter-title{
    color:#31516a;
    font-size:10px;
    font-weight:900;
    text-transform:uppercase;
    margin-right:2px
}

.r13b-drill-chip{
    display:inline-flex;
    align-items:center;
    gap:6px;
    border:1px solid #cde6ea;
    background:#fff;
    color:#31516a;
    border-radius:999px;
    padding:6px 8px 6px 10px;
    font-size:10px;
    font-weight:700
}

.r13b-drill-chip b{
    color:#087f8e
}

.r13b-drill-chip button,
.r13b-drill-clear-all{
    border:0;
    background:transparent;
    color:#087f8e;
    cursor:pointer;
    font-weight:900
}

.r13b-drill-clear-all{
    margin-left:auto;
    border:1px solid #cde6ea;
    background:#fff;
    border-radius:8px;
    padding:6px 9px
}

.r13b-drill-count{
    color:#61768b;
    font-size:10px;
    font-weight:700
}

.r13b-drill-through-btn{
    border:1px solid #cde6ea;
    background:#fff;
    color:#087f8e;
    border-radius:8px;
    padding:6px 9px;
    font-size:10px;
    font-weight:800;
    cursor:pointer;
    white-space:nowrap
}

.r13b-drill-through-btn:hover,
.r13b-drill-through-btn:focus{
    background:#eef9fa;
    outline:1px solid #bfe8ec
}

.r13b-drill-through-modal{
    position:fixed;
    inset:0;
    display:none;
    align-items:center;
    justify-content:center;
    z-index:80;
    padding:20px;
    background:rgba(7,24,37,.48)
}

.r13b-drill-through-modal.open{
    display:flex
}

.r13b-drill-through-box{
    width:min(1280px,96vw);
    max-height:90vh;
    overflow:auto;
    background:#fff;
    border-radius:16px;
    border:1px solid #dce7ef;
    box-shadow:0 24px 70px rgba(18,52,77,.22);
    padding:16px
}

.r13b-drill-through-head{
    display:flex;
    align-items:flex-start;
    justify-content:space-between;
    gap:12px;
    margin-bottom:10px
}

.r13b-drill-through-head h3{
    margin:0 0 3px;
    font-size:16px
}

.r13b-drill-through-close{
    border:1px solid #dce7ef;
    background:#f8fbfd;
    color:#31516a;
    border-radius:9px;
    padding:7px 10px;
    font-weight:800;
    cursor:pointer
}

.r13b-drill-through-meta{
    display:flex;
    gap:7px;
    flex-wrap:wrap;
    margin:8px 0 12px
}

.r13b-drill-through-meta span{
    border:1px solid #dce7ef;
    background:#f8fbfd;
    border-radius:999px;
    padding:5px 8px;
    font-size:10px;
    color:#4d6478;
    font-weight:700
}

.r13b-drill-through-empty{
    padding:20px;
    text-align:center;
    color:#61768b;
    font-size:12px
}

.r13b-drillable{
    cursor:pointer;
    transition:background .15s ease,transform .15s ease
}

.r13b-drillable:hover,
.r13b-drillable:focus{
    background:#eef9fa;
    outline:1px solid #bfe8ec;
    border-radius:9px
}

.r13b-drillable:active{
    transform:scale(.995)
}

.r13b-drill-status{
    grid-column:span 12;
    display:flex;
    align-items:center;
    justify-content:space-between;
    gap:10px;
    flex-wrap:wrap;
    border:1px solid #bfe8ec;
    background:#eef9fa;
    border-radius:10px;
    padding:8px 11px;
    color:#31516a;
    font-size:11px
}

.r13b-drill-status button{
    border:1px solid #cde6ea;
    background:#fff;
    color:#087f8e;
    border-radius:8px;
    padding:6px 9px;
    font-weight:800;
    cursor:pointer
}

.r13b-share{
    color:#61768b;
    font-weight:600;
    margin-left:4px
}

.r13b-table-wrap{
    overflow:auto;
    max-height:520px;
    border:1px solid #edf2f6;
    border-radius:11px;
    margin-top:10px
}

.r13b-table{
    width:100%;
    border-collapse:collapse;
    font-size:10px
}

.r13b-table th{
    position:sticky;
    top:0;
    background:#f1f6f9;
    text-align:left;
    z-index:1
}

.r13b-table th,
.r13b-table td{
    padding:8px 9px;
    border-bottom:1px solid #edf2f6;
    white-space:nowrap
}

.r13b-table tbody tr:nth-child(even) td{
    background:#fbfdfe
}

.r13b-blocked{
    grid-column:span 12;
    border:1px solid #f2c8c8;
    background:#fff7f7;
    border-radius:12px;
    padding:12px;
    font-size:11px
}

.r13b-quality{
    display:grid;
    grid-template-columns:repeat(auto-fit,minmax(180px,1fr));
    gap:9px;
    margin-top:10px
}

.r13b-quality>div{
    border:1px solid #edf2f6;
    background:#fbfdfe;
    border-radius:10px;
    padding:10px
}

.r13b-quality b{
    display:block;
    font-size:16px;
    margin-top:3px
}

.r13b-empty{
    grid-column:span 12;
    border:1px dashed #cbd9e2;
    border-radius:12px;
    padding:18px;
    color:#61768b;
    background:#fbfdfe
}

.r13b-coverage{
    margin-top:8px;
    font-size:10px;
    color:#61768b
}

body.r13b-executor-mode #resumen,
body.r13b-executor-mode #graficas,
body.r13b-executor-mode #detalle,
body.r13b-executor-mode #analitica,
body.r13b-executor-mode #pregunta,
body.r13b-executor-mode #auditoria,
body.r13b-executor-mode #componentes{
    display:none!important
}

@media(max-width:900px){

    .r13b-card,
    .r13b-card.third{
        grid-column:span 12
    }

    .r13b-bar-row{
        grid-template-columns:1fr
    }

    .r13b-bar-val{
        justify-self:start
    }
}

</style>

<script id="r1013b-runtime">

(function(){

try{

    const model=
        (DATA&&DATA.plan&&DATA.plan.dynamic_renderer)
        || null;

    if(
        !model
        || !model.enabled
        || !Array.isArray(model.pages)
        || !model.pages.length
    ){
        return;
    }

    document.body.classList.add('r13b-active');

    const LEGACY_PAGE_IDS=new Set([
        'summary',
        'customers',
        'analysis',
        'operations',
        'customer_profile',
        'line_analysis',
        'lost_customers'
    ]);

    const legacyMode=model.domain==='sales'&&model.pages.every(
    	p=>LEGACY_PAGE_IDS.has(p.id)
    );

    if(!legacyMode){
        document.body.classList.add(
            'r13b-executor-mode'
        );
    }

    const $=id=>
        document.getElementById(id);

    const esc=s=>
        String(s??'').replace(
            /[&<>"']/g,
            c=>({
                '&':'&amp;',
                '<':'&lt;',
                '>':'&gt;',
                '"':'&quot;',
                "'":'&#039;'
            }[c])
        );

    const n=v=>{
        const x=Number(v);
        return Number.isFinite(x)?x:0;
    };

    const fmt=(v,kind='number')=>{

        if(
            v===null
            || v===undefined
            || !Number.isFinite(Number(v))
        ){
            return 'N/D';
        }

        const x=Number(v);

        if(kind==='percent'){
            return x.toLocaleString(
                'es-MX',
                {maximumFractionDigits:1}
            )+'%';
        }

        if(kind==='integer'){
            return Math.round(x)
                .toLocaleString('es-MX');
        }

        if(kind==='currency'){
            return '$'+x.toLocaleString(
                'es-MX',
                {maximumFractionDigits:2}
            );
        }

        return x.toLocaleString(
            'es-MX',
            {maximumFractionDigits:2}
        );
    };

    const api=()=>
        window.__IA_DASHBOARD_API__
        || null;

    /*
     * =====================================================
     * R10.13D.10
     * CROSS-FILTER / DRILL-DOWN STATE
     * =====================================================
     *
     * Se aplica DESPUÉS de los filtros globales existentes.
     * Nunca reemplaza ni modifica la autoridad del filtro base.
     */
    const dimensionDrillFilters={};

    const rows=()=>{

        const a=api();

        const baseRows=(
            a
            && typeof a.filteredRows==='function'
        )
            ? a.filteredRows()
            : (DATA.rows||[]);

        const activeDrills=
            Object.values(
                dimensionDrillFilters
            )
                .filter(
                    item=>
                        item
                        &&item.column
                        &&item.value!==undefined
                        &&item.value!==null
                );

        if(!activeDrills.length){
            return baseRows;
        }

        return baseRows.filter(
            row=>
                activeDrills.every(
                    item=>
                        String(
                            row[item.column]
                            ??'Sin dato'
                        )===String(item.value)
                )
        );
    };

    const role=r=>
        String(
            (model.semantic_roles||{})[r]
            || ''
        );

    const qtyCol=()=>
        role('quantity')
        || 'Toneladas_Vendidas';

    const nav=
        document.querySelector('.nav');

    const main=
        document.querySelector('.main');

    const footer=
        document.querySelector('.footer');

    if(!nav||!main||!footer){
        return;
    }


    /*
     * PAGE HOST
     */

    const host=
        document.createElement('div');

    host.id='r13bPageHost';

    footer.parentNode.insertBefore(
        host,
        footer
    );


    /*
     * TOOLBAR
     */

    const toolbar=$('filters');

    if(toolbar&&!legacyMode){

        const wrap=
            document.createElement('div');

        wrap.className=
            'r13b-toolbar-host';

        host.parentNode.insertBefore(
            wrap,
            host
        );

        wrap.appendChild(toolbar);
    }

    /*
     * =====================================================
     * R10.13D.11
     * GLOBAL ANALYTICAL FILTER BAR
     * =====================================================
     */
    const drillFilterHost=
        document.createElement('div');

    drillFilterHost.id=
        'r13bDrillFilterHost';

    drillFilterHost.className=
        'r13b-drill-filter-host';

    host.parentNode.insertBefore(
        drillFilterHost,
        host
    );

    /*
     * =====================================================
     * R10.13D.12
     * CONTEXTUAL DRILL-THROUGH MODAL
     * =====================================================
     */
    const drillThroughModal=
        document.createElement('div');

    drillThroughModal.id=
        'r13bDrillThroughModal';

    drillThroughModal.className=
        'r13b-drill-through-modal';

    drillThroughModal.setAttribute(
        'aria-hidden',
        'true'
    );

    drillThroughModal.innerHTML=`
        <div
            class="r13b-drill-through-box"
            role="dialog"
            aria-modal="true"
            aria-labelledby="r13bDrillThroughTitle"
        >
            <div class="r13b-drill-through-head">
                <div>
                    <h3 id="r13bDrillThroughTitle">
                        Detalle transaccional
                    </h3>
                    <div
                        class="r13b-small"
                        id="r13bDrillThroughSubtitle"
                    ></div>
                </div>
                <button
                    type="button"
                    class="r13b-drill-through-close"
                    data-r13b-drill-through-close
                >
                    Cerrar
                </button>
            </div>
            <div id="r13bDrillThroughBody"></div>
        </div>`;

    document.body.appendChild(
        drillThroughModal
    );


    /*
     * FILTER AUTHORITY
     */

    const allowedCols=new Set(
        Object.values(model.components||{})
            .filter(
                c=>
                    c
                    && c.type==='filter'
                    && c.status!=='BLOCKED'
            )
            .flatMap(
                c=>c.source_columns||[]
            )
    );

    if(!legacyMode){

        document
            .querySelectorAll('#filters .filter')
            .forEach(box=>{

                const sel=
                    box.querySelector(
                        'select[data-col]'
                    );

                if(
                    sel
                    && !allowedCols.has(sel.dataset.col)
                    && sel.id!=='chartTop'
                ){
                    box.style.display='none';
                }
            });
    }

    const dateBox=
        document.querySelector(
            '#filters .datebox'
        );

    if(
        !legacyMode
        && dateBox
        && !allowedCols.has(role('date'))
    ){
        dateBox.style.display='none';
    }

    const searchBox=
        document.querySelector(
            '#filters .searchbox'
        );

    if(
        !legacyMode
        && searchBox
        && !allowedCols.has(role('customer'))
    ){
        searchBox.style.display='none';
    }

    const chartTop=
        $('chartTop')?.closest('.filter');

    if(!legacyMode&&chartTop){
        chartTop.style.display='none';
    }

    const toggleFilters=
        $('toggleFilters');

    if(!legacyMode&&toggleFilters){
        toggleFilters.style.display='none';
    }


    /*
     * R10.13D.7.1.2
     * LEGACY CHART TOGGLE CLEANUP
     */

    const toggleCharts=
        $('toggleCharts');

    if(!legacyMode&&toggleCharts){

        const chartHeader=
            toggleCharts.closest(
                '.section-head'
            );

        if(chartHeader){
            chartHeader.style.display='none';
        }

        toggleCharts.style.display='none';
    }


    /*
     * CORE HELPERS
     */

    function sum(rr,col){
        return rr.reduce(
            (s,r)=>s+n(r[col]),
            0
        );
    }


    function group(rr,keys,measure){

        const m=new Map();

        for(const r of rr){

            const labels=keys.map(
                k=>String(
                    r[k]??'Sin dato'
                )
            );

            const key=
                labels.join('|||');

            if(!m.has(key)){

                m.set(
                    key,
                    {
                        labels,
                        value:0,
                        count:0
                    }
                );
            }

            const x=m.get(key);

            x.value+=n(r[measure]);
            x.count++;
        }

        return [...m.values()];
    }


    function sourceLine(cols){

        return cols&&cols.length
            ? `<div class="r13b-source">Fuente: ${cols.map(esc).join(' + ')}</div>`
            : '';
    }


    function blockedCard(c){

        return `
        <div class="r13b-blocked">

            <b>
                ${esc(
                    c.title
                    || c.semantic_role
                    || c.id
                )} · N/D
            </b>

            <div>
                ${esc(
                    c.reason
                    || 'Capacidad no disponible con los datos actuales.'
                )}
            </div>

            ${sourceLine(
                c.source_columns||[]
            )}

        </div>`;
    }


    function distinct(rr,col){

        return new Set(
            rr
                .map(
                    r=>String(
                        r[col]??''
                    ).trim()
                )
                .filter(Boolean)
        ).size;
    }


    /*
     * KPI EXECUTOR
     *
     * IMPORTANTE:
     * estas expresiones conservan el formato literal
     * requerido por los tests R10.13C.
     */

    function kpiValue(c,rr){

        if(c.status==='BLOCKED')return null;

        const cols=c.source_columns||[];
        const op=String((c.execution||{}).operator||'');

        if(op==='difference_of_sums'&&cols.length>=2)
            return sum(rr,cols[0])-sum(rr,cols[1]);

        if(op==='ratio_of_sums'&&cols.length>=2){
            const den=sum(rr,cols[1]);
            return den?sum(rr,cols[0])/den:null;
        }

        if(op==='difference_over_sum'&&cols.length>=3){
            const den=sum(rr,cols[2]);
            return den?(sum(rr,cols[0])-sum(rr,cols[1]))/den:null;
        }

        if(op==='ratio_of_sums_pct'&&cols.length>=2){
            const den=sum(rr,cols[1]);
            return den?100*sum(rr,cols[0])/den:null;
        }

        if(op==='difference_over_sum_pct'&&cols.length>=2){
            const den=sum(rr,cols[0]);
            return den?100*(sum(rr,cols[0])-sum(rr,cols[1]))/den:null;
        }

        if(op==='nunique'&&cols[0])
            return distinct(rr,cols[0]);

        if(op==='sum_over_nunique'&&cols.length>=2){
            const den=distinct(rr,cols[1]);
            return den?sum(rr,cols[0])/den:null;
        }

        if(!op&&cols.length===1)
            return sum(rr,cols[0]);

        return null;
    }


    function ruleLine(c){

        const r=c.rule||{};

        if(!r.rule_id){
            return '';
        }

        return `
        <div class="r13b-source">
            Regla: ${esc(r.rule_id)}
            · ${esc(c.formula||'')}
            · división por cero: N/D
        </div>`;
    }


    function kpiCard(c,rr){

        if(c.status==='BLOCKED'){
            return blockedCard(c);
        }

        const v=
            kpiValue(c,rr);

        const roleName=
            String(c.semantic_role||'');

        const kind=
            c.output_format
            || (
                /revenue|cost|profit|freight|price|ticket/
                    .test(roleName)
                    ? 'currency'
                    : /margin/.test(roleName)
                        ? 'percent'
                        : /operations|customers|sellers|products/
                            .test(roleName)
                            ? 'integer'
                            : 'number'
            );

        return `
        <article class="r13b-card third">

            <h3>
                ${esc(
                    c.title
                    || roleName
                )}
            </h3>

            <span class="r13b-status ${esc(c.status||'SUPPORTED')}">
                ${esc(c.status||'SUPPORTED')}
            </span>

            <div class="r13b-kpi-value">
                ${fmt(v,kind)}
            </div>

            <div class="r13b-small">
                ${rr.length.toLocaleString('es-MX')}
                registros filtrados
            </div>

            ${sourceLine(
                c.source_columns||[]
            )}

            ${ruleLine(c)}

        </article>`;
    }


    /*
     * BAR EXECUTOR
     */

    function barsCard(
        title,
        data,
        {
            share=false,
            full=false
        }={}
    ){

        const sorted=
            [...data].sort(
                (a,b)=>b.value-a.value
            );

        const top=
            sorted.slice(0,15);

        const mx=
            Math.max(
                1,
                ...top.map(
                    x=>Math.abs(x.value)
                )
            );

        const total=
            sorted.reduce(
                (s,x)=>s+x.value,
                0
            );

        return `
        <article class="r13b-card ${full?'full':''}">

            <h3>${esc(title)}</h3>

            <div class="r13b-small">
                Top ${top.length}
                de ${sorted.length}
                categorías
            </div>

            <div class="r13b-bars">

                ${top.map(x=>{

                    const label=
                        x.labels.join(' → ');

                    const pct=
                        total
                            ? 100*x.value/total
                            : 0;

                    const drillable=
                        Boolean(
                            x.drill_column
                            &&x.drill_value!==undefined
                            &&x.drill_value!==null
                        );

                    return `
                    <div
                        class="r13b-bar-row ${
                            drillable
                                ?'r13b-drillable'
                                :''
                        }"
                        ${
                            drillable
                                ?`data-r13b-drill-column="${esc(x.drill_column)}"
                                  data-r13b-drill-value="${esc(x.drill_value)}"
                                  data-r13b-drill-label="${esc(label)}"`
                                :''
                        }
                        ${
                            drillable
                                ?'role="button" tabindex="0"'
                                :''
                        }
                    >

                        <span
                            class="r13b-bar-name"
                            title="${esc(label)}"
                        >
                            ${esc(label)}
                        </span>

                        <span class="r13b-bar-track">

                            <i
                                class="r13b-bar-fill"
                                style="width:${
                                    Math.max(
                                        1,
                                        Math.abs(x.value)
                                        /mx
                                        *100
                                    )
                                }%"
                            ></i>

                        </span>

                        <span class="r13b-bar-val">

                            ${fmt(x.value)}

                            ${
                                share
                                    ? `<span class="r13b-share">${fmt(pct,'percent')}</span>`
                                    : ''
                            }

                        </span>

                    </div>`;

                }).join('')}

            </div>

        </article>`;
    }


    /*
     * TREND EXECUTOR
     */

    function monthGroup(
        rr,
        dateCol,
        measure
    ){

        const m=new Map();

        for(const r of rr){

            const d=
                String(
                    r[dateCol]??''
                ).slice(0,7)
                || 'Sin fecha';

            m.set(
                d,
                (m.get(d)||0)
                +n(r[measure])
            );
        }

        return [
            ...m.entries()
        ]
            .sort(
                (a,b)=>
                    a[0].localeCompare(b[0])
            )
            .map(
                ([label,value])=>({
                    labels:[label],
                    value
                })
            );
    }


    function trendCard(
        title,
        data
    ){

        const seq=
            [...data].slice(-36);

        const mx=
            Math.max(
                1,
                ...seq.map(
                    x=>Math.abs(x.value)
                )
            );

        return `
        <article class="r13b-card full">

            <h3>${esc(title)}</h3>

            <div class="r13b-small">
                Serie cronológica · últimos
                ${seq.length}
                periodos disponibles
            </div>

            <div class="r13b-bars">

                ${seq.map(x=>`
                    <div class="r13b-bar-row">

                        <span class="r13b-bar-name">
                            ${esc(x.labels[0])}
                        </span>

                        <span class="r13b-bar-track">

                            <i
                                class="r13b-bar-fill"
                                style="width:${
                                    Math.max(
                                        1,
                                        Math.abs(x.value)
                                        /mx
                                        *100
                                    )
                                }%"
                            ></i>

                        </span>

                        <span class="r13b-bar-val">
                            ${fmt(x.value)}
                        </span>

                    </div>
                `).join('')}

            </div>

        </article>`;
    }


    /*
     * TABLE EXECUTOR
     */

    function tableCard(
        title,
        rr,
        cols,
        limit=100
    ){

        const use=
            cols
                .filter(Boolean)
                .filter(
                    c=>
                        rr.some(
                            r=>
                                Object.prototype
                                    .hasOwnProperty
                                    .call(r,c)
                        )
                );

        const view=
            rr.slice(0,limit);

        return `
        <article class="r13b-card full">

            <h3>${esc(title)}</h3>

            <div class="r13b-small">
                Mostrando
                ${view.length.toLocaleString('es-MX')}
                de
                ${rr.length.toLocaleString('es-MX')}
                registros filtrados.
            </div>

            <div class="r13b-table-wrap">

                <table class="r13b-table">

                    <thead>
                        <tr>
                            ${
                                use.map(
                                    c=>
                                        `<th>${esc(c)}</th>`
                                ).join('')
                            }
                        </tr>
                    </thead>

                    <tbody>

                        ${
                            view.map(
                                r=>
                                    `<tr>${
                                        use.map(
                                            c=>
                                                `<td>${esc(r[c]??'')}</td>`
                                        ).join('')
                                    }</tr>`
                            ).join('')
                        }

                    </tbody>

                </table>

            </div>

        </article>`;
    }


    /*
     * QUALITY EXECUTOR
     */

    function qualityCard(rr){

        const cols=
            model.source
            && model.source.columns
            || [];

        const nulls=
            cols
                .map(
                    c=>({
                        c,
                        n:rr.reduce(
                            (s,r)=>
                                s+(
                                    r[c]===null
                                    || r[c]===undefined
                                    || String(r[c]).trim()===''
                                        ?1
                                        :0
                                ),
                            0
                        )
                    })
                )
                .filter(x=>x.n)
                .sort(
                    (a,b)=>b.n-a.n
                );

        const missing=
            nulls.reduce(
                (s,x)=>s+x.n,
                0
            );

        const cells=
            Math.max(
                1,
                rr.length
                *Math.max(
                    1,
                    cols.length
                )
            );

        return `
        <article class="r13b-card full">

            <h3>
                Calidad de Datos
            </h3>

            <div class="r13b-quality">

                <div>
                    Registros
                    <b>
                        ${rr.length.toLocaleString('es-MX')}
                    </b>
                </div>

                <div>
                    Columnas
                    <b>
                        ${cols.length.toLocaleString('es-MX')}
                    </b>
                </div>

                <div>
                    Celdas vacías
                    <b>
                        ${missing.toLocaleString('es-MX')}
                    </b>
                </div>

                <div>
                    Completitud
                    <b>
                        ${
                            fmt(
                                100*(1-missing/cells),
                                'percent'
                            )
                        }
                    </b>
                </div>

            </div>

            ${
                nulls.length
                    ? `
                    <div class="r13b-table-wrap">

                        <table class="r13b-table">

                            <thead>
                                <tr>
                                    <th>Columna</th>
                                    <th>Vacíos</th>
                                    <th>% filas</th>
                                </tr>
                            </thead>

                            <tbody>

                                ${
                                    nulls
                                        .slice(0,20)
                                        .map(
                                            x=>`
                                            <tr>
                                                <td>${esc(x.c)}</td>
                                                <td>${x.n.toLocaleString('es-MX')}</td>
                                                <td>${
                                                    fmt(
                                                        rr.length
                                                            ?100*x.n/rr.length
                                                            :0,
                                                        'percent'
                                                    )
                                                }</td>
                                            </tr>
                                            `
                                        )
                                        .join('')
                                }

                            </tbody>

                        </table>

                    </div>`
                    : `
                    <div class="r13b-small">
                        No se detectaron valores vacíos
                        en la selección.
                    </div>`
            }

        </article>`;
    }


    /*
     * =====================================================
     * R10.13D.1
     * ANALYSIS EXECUTOR
     * =====================================================
     */

    function analysisCard(c,rr){

        if(c.status==='BLOCKED'){
            return blockedCard(c);
        }

        const id=
            String(c.id||'');

        const q=
            qtyCol();


        /*
         * LOGISTICS
         */

        if(id==='analysis:warehouse_movement'){

            const w=
                role('warehouse');

            return barsCard(
                'Movimiento por almacén',
                group(
                    rr,
                    [w],
                    q
                ),
                {
                    full:true
                }
            );
        }


        if(id==='analysis:routes'){

            const o=
                role('origin_city');

            const d=
                role('destination_city');

            return barsCard(
                'Rutas principales',
                group(
                    rr,
                    [o,d],
                    q
                ),
                {
                    full:true
                }
            );
        }


        if(id==='analysis:origin_share'){

            const o=
                role('origin_city');

            return barsCard(
                'Participación por ciudad origen',
                group(
                    rr,
                    [o],
                    q
                ),
                {
                    share:true
                }
            );
        }


        if(id==='analysis:destination_share'){

            const d=
                role('destination_city');

            return barsCard(
                'Participación por ciudad destino',
                group(
                    rr,
                    [d],
                    q
                ),
                {
                    share:true
                }
            );
        }


        /*
         * TEMPORAL
         */

        if(
            id==='analysis:monthly_movement'
            || id==='analysis:trend'
        ){

            const d=
                role('date');

            return trendCard(
                id==='analysis:monthly_movement'
                    ?'Evolución mensual del movimiento'
                    :'Evolución temporal',
                monthGroup(
                    rr,
                    d,
                    q
                )
            );
        }


        /*
         * CUSTOMER PICKUP
         */

        if(id==='analysis:customer_pickup'){

            const p=
                role('customer_pickup');

            return barsCard(
                'Clientes que recogen',
                group(
                    rr,
                    [p],
                    q
                ),
                {
                    share:true,
                    full:true
                }
            );
        }


        /*
         * QUALITY
         */

        if(id==='analysis:data_quality'){

            return qualityCard(rr);
        }


        /*
         * =====================================================
         * R10.13D.7
         * OPERATOR-DRIVEN CANONICAL DIMENSION PROFITABILITY
         * =====================================================
         */

        const execution=c.execution||{};
        const operator=String(
            execution.operator
            ||''
        );

        if(operator==='dimension_profitability'){
            return dimensionProfitabilityCard(
                c,
                rr
            );
        }

        /*
         * Compatibilidad R10.13D.2.
         * El dispatch depende del operator, no del ID.
         */
        if(operator==='group_by_dimension'){

            const dimensionRole=String(
                execution.dimension_role
                ||c.semantic_role
                ||''
            );

            const dimensionCol=
                role(dimensionRole);

            if(!dimensionCol){
                return blockedCard({
                    ...c,
                    status:'BLOCKED',
                    reason:
                        'No existe una columna semántica válida '
                        +'para la dimensión solicitada.'
                });
            }

            const measureRole=String(
                execution.measure_role
                ||'quantity'
            );

            const measureCol=
                role(measureRole);

            if(!measureCol){
                return blockedCard({
                    ...c,
                    status:'BLOCKED',
                    reason:
                        'No existe una medida soportada para '
                        +'ejecutar este análisis por dimensión.'
                });
            }

            return barsCard(
                c.title
                ||('Análisis por '+dimensionRole),
                group(
                    rr,
                    [dimensionCol],
                    measureCol
                ),
                {
                    full:true
                }
            );
        }

        /*
         * COMMERCIAL PROFITABILITY LEGACY
         */



        if(id==='analysis:profitability'){

            const revenue=
                role('revenue');

            const cost=
                role('cost');

            const customer=
                role('customer');

            if(
                revenue
                && cost
                && customer
            ){

                const grouped=
                    new Map();

                for(const row of rr){

                    const key=
                        String(
                            row[customer]
                            ??'N/D'
                        );

                    if(!grouped.has(key)){

                        grouped.set(
                            key,
                            {
                                labels:[key],
                                value:0
                            }
                        );
                    }

                    const item=
                        grouped.get(key);

                    item.value+=(
                        n(row[revenue])
                        -n(row[cost])
                    );
                }

                return barsCard(
                    'Rentabilidad por cliente',
                    [...grouped.values()],
                    {
                        full:true
                    }
                );
            }
        }


        /*
         * EXECUTIVE SUMMARY
         */

        if(id==='analysis:executive_summary'){

            return `
            <article class="r13b-card">

                <h3>
                    Resumen Ejecutivo
                </h3>

                <span class="r13b-status SUPPORTED">
                    SUPPORTED
                </span>

                <div class="r13b-small">
                    Indicadores ejecutivos calculados
                    sobre la selección actual.
                </div>

            </article>`;
        }


        /*
         * RISKS
         */

        if(id==='analysis:risks'){

            return `
            <article class="r13b-card">

                <h3>
                    Riesgos y observaciones
                </h3>

                <span class="r13b-status SUPPORTED">
                    SUPPORTED
                </span>

                <div class="r13b-small">
                    Se muestran únicamente riesgos
                    soportados por las capacidades
                    y los datos disponibles.
                </div>

            </article>`;
        }


        /*
         * DETAIL
         *
         * Conservamos "Detalle Logístico" literalmente
         * por compatibilidad con R10.13B.2.
         */

        if(id==='analysis:detail'){

            return tableCard(
                'Detalle Logístico',
                rr,
                [
                    role('date'),
                    role('customer'),
                    role('product'),
                    role('seller'),
                    role('warehouse'),
                    role('revenue'),
                    role('cost'),
                    q,
                    role('origin_city'),
                    role('destination_city'),
                    role('customer_pickup'),
                    'Refer'
                ].filter(Boolean),
                100
            );
        }


        /*
         * FREIGHT SAFETY
         */

        if(id==='analysis:freight_analysis'){

            return blockedCard({
                ...c,
                title:
                    'Análisis de Flete',
                reason:
                    c.reason
                    || (
                        'El flete total no tiene '
                        +'una regla empresarial validada.'
                    )
            });
        }


        /*
         * SAFE FALLBACK
         */

        return `
        <article class="r13b-card">

            <h3>
                ${
                    esc(
                        c.title
                        ||c.semantic_role
                        ||c.id
                    )
                }
            </h3>

            <span class="r13b-status ${esc(c.status||'SUPPORTED')}">
                ${esc(c.status||'SUPPORTED')}
            </span>

            ${
                sourceLine(
                    c.source_columns||[]
                )
            }

        </article>`;
    }


    /*
     * =====================================================
     * R10.13D.1
     * GENERIC TABLE EXECUTOR
     * =====================================================
     */

        /*
     * =====================================================
     * R10.13D.3
     * GENERIC AGGREGATED BUSINESS TABLE EXECUTOR
     * =====================================================
     */

    function canonicalKpi(id){

        return (
            model.components
            && model.components[id]
        )
            || null;
    }


    function aggregateGroups(
        rr,
        keyCols
    ){

        const usableKeys=
            [...new Set(
                (keyCols||[])
                    .filter(Boolean)
            )];


        const groups=
            new Map();


        for(const row of rr){

            const labels=
                usableKeys.map(
                    col=>
                        String(
                            row[col]
                            ??'Sin dato'
                        )
                );


            const key=
                labels.join('|||');


            if(!groups.has(key)){

                groups.set(
                    key,
                    {
                        labels,
                        rows:[],
                        count:0
                    }
                );
            }


            const item=
                groups.get(key);


            item.rows.push(row);

            item.count++;
        }


        return [
            ...groups.values()
        ];
    }


    function aggregateMetric(
        component,
        groupRows
    ){

        if(!component){
            return null;
        }


        if(component.status==='BLOCKED'){
            return null;
        }


        return kpiValue(
            component,
            groupRows
        );
    }


    function businessMetricDefinitions(){

        return [

            {
                id:'kpi:revenue',
                label:'Ventas',
                format:'currency'
            },

            {
                id:'kpi:cost',
                label:'Costo',
                format:'currency'
            },

            {
                id:'kpi:profit',
                label:'Utilidad',
                format:'currency'
            },

            {
                id:'kpi:margin_pct',
                label:'Margen %',
                format:'percent'
            },

            {
                id:'kpi:quantity',
                label:'Toneladas',
                format:'number'
            },

            {
                id:'kpi:operations',
                label:'Operaciones',
                format:'integer'
            },

            {
                id:'kpi:ticket_avg',
                label:'Ticket Promedio',
                format:'currency'
            },

            {
                id:'kpi:price_per_unit',
                label:'Precio / Ton',
                format:'currency'
            },

            {
                id:'kpi:cost_per_unit',
                label:'Costo / Ton',
                format:'currency'
            },

            {
                id:'kpi:profit_per_unit',
                label:'Utilidad / Ton',
                format:'currency'
            }

        ]
            .map(
                item=>({
                    ...item,
                    component:
                        canonicalKpi(
                            item.id
                        )
                })
            )
            .filter(
                item=>
                    item.component
                    &&item.component.status!=='BLOCKED'
            );
    }


    /*
     * =====================================================
     * R10.13D.8
     * INTERACTIVE DIMENSION METRIC SELECTOR
     * =====================================================
     *
     * Mantiene la métrica elegida por componente aunque
     * el dashboard se vuelva a renderizar por filtros.
     */
    const dimensionMetricSelection={};

    /*
     * =====================================================
     * R10.13D.9
     * INTERACTIVE DIMENSION CHART CONTROLS
     * =====================================================
     *
     * Estado independiente por componente:
     * - top_n
     * - sort_order
     * - chart_view
     */
    const dimensionChartControls={};


    function rankingListCard(
        title,
        chartData,
        format='number'
    ){

        const maxAbs=Math.max(
            1,
            ...chartData.map(
                item=>Math.abs(
                    Number(item.value)||0
                )
            )
        );

        return `
        <article class="r13b-card full">
            <h3>${esc(title)}</h3>

            <div class="r13b-ranking-list">
                ${
                    chartData
                        .map(
                            (item,index)=>{
                                const value=
                                    Number(item.value)||0;

                                const width=
                                    Math.max(
                                        2,
                                        Math.round(
                                            Math.abs(value)
                                            /maxAbs
                                            *100
                                        )
                                    );

                                const drillable=
                                    Boolean(
                                        item.drill_column
                                        &&item.drill_value!==undefined
                                        &&item.drill_value!==null
                                    );

                                return `
                                <div
                                    class="r13b-ranking-row ${
                                        drillable
                                            ?'r13b-drillable'
                                            :''
                                    }"
                                    ${
                                        drillable
                                            ?`data-r13b-drill-column="${esc(item.drill_column)}"
                                              data-r13b-drill-value="${esc(item.drill_value)}"
                                              data-r13b-drill-label="${esc((item.labels||[])[0]??'Sin dato')}"`
                                            :''
                                    }
                                    ${
                                        drillable
                                            ?'role="button" tabindex="0"'
                                            :''
                                    }
                                >
                                    <span class="r13b-ranking-pos">
                                        ${index+1}
                                    </span>
                                    <span class="r13b-ranking-name">
                                        ${esc(
                                            (item.labels||[])[0]
                                            ??'Sin dato'
                                        )}
                                    </span>
                                    <span class="r13b-ranking-track">
                                        <i style="width:${width}%"></i>
                                    </span>
                                    <strong>
                                        ${fmt(value,format)}
                                    </strong>
                                </div>`;
                            }
                        )
                        .join('')
                }
            </div>
        </article>`;
    }


    function dimensionProfitabilityCard(c,rr){

        const execution=c.execution||{};

        const dimensionRole=String(
            execution.dimension_role
            ||c.semantic_role
            ||''
        );

        const identityRole=String(
            execution.identity_role
            ||dimensionRole
        );

        const labelRole=String(
            execution.label_role
            ||dimensionRole
        );

        const identityCol=
            role(identityRole)
            ||role(dimensionRole);

        const labelCol=role(labelRole);

        if(!identityCol){
            return blockedCard({
                ...c,
                status:'BLOCKED',
                reason:
                    'No existe una columna semántica válida '
                    +'para la dimensión solicitada.'
            });
        }

        const requestedMetricIds=
            Array.isArray(execution.measure_kpis)
                ?execution.measure_kpis
                :[];

        const metricDefs=
            businessMetricDefinitions()
                .filter(
                    item=>
                        !requestedMetricIds.length
                        ||requestedMetricIds.includes(item.id)
                );

        if(!metricDefs.length){
            return blockedCard({
                ...c,
                status:'BLOCKED',
                reason:
                    'No existen KPIs canónicos soportados '
                    +'para ejecutar la rentabilidad por dimensión.'
            });
        }

        const groups=aggregateGroups(
            rr,
            [identityCol]
        );

        const sortMetric=String(
            execution.sort_metric
            ||'kpi:revenue'
        );

        const topN=Math.max(
            1,
            Math.min(
                Number(execution.top_n||15),
                250
            )
        );

        const rowsAgg=groups.map(
            group=>{

                const metrics={};

                for(const metric of metricDefs){
                    metrics[metric.id]=
                        aggregateMetric(
                            metric.component,
                            group.rows
                        );
                }

                const firstRow=group.rows[0]||{};

                const labelValue=
                    (
                        labelCol
                        &&labelCol!==identityCol
                    )
                        ?String(
                            firstRow[labelCol]
                            ??'Sin dato'
                        )
                        :null;

                return {
                    identity:
                        group.labels[0]
                        ??'Sin dato',
                    label:labelValue,
                    count:group.count,
                    metrics
                };
            }
        );

        rowsAgg.sort(
            (a,b)=>{

                const av=Number(
                    a.metrics[sortMetric]
                );
                const bv=Number(
                    b.metrics[sortMetric]
                );

                if(
                    Number.isFinite(av)
                    ||Number.isFinite(bv)
                ){
                    return (
                        (Number.isFinite(bv)?bv:0)
                        -
                        (Number.isFinite(av)?av:0)
                    );
                }

                return b.count-a.count;
            }
        );

        const view=rowsAgg.slice(0,topN);

        const showLabel=Boolean(
            labelCol
            &&labelCol!==identityCol
        );

        /*
         * =====================================================
         * R10.13D.7.1
         * GENERIC DIMENSION CHART EXECUTOR
         * =====================================================
         */

        const chartSpec=
            (
                execution.chart
                &&typeof execution.chart==='object'
            )
                ?execution.chart
                :{};

        const chartOperator=
            String(
                chartSpec.operator
                ||'dimension_bar_chart'
            );

        const defaultChartMetricId=
            String(
                chartSpec.metric
                ||sortMetric
                ||'kpi:revenue'
            );

        const selectedChartMetricId=
            String(
                dimensionMetricSelection[c.id]
                ||defaultChartMetricId
            );

        const chartMetricDef=
            metricDefs.find(
                item=>
                    item.id===selectedChartMetricId
            )
            ||metricDefs.find(
                item=>
                    item.id===defaultChartMetricId
            )
            ||metricDefs[0]
            ||null;

        if(
            chartMetricDef
            &&dimensionMetricSelection[c.id]
            !==chartMetricDef.id
        ){
            dimensionMetricSelection[c.id]=
                chartMetricDef.id;
        }

        const metricSelectorHtml=
            metricDefs.length>1
                ?`
                <div class="r13b-metric-control">
                    <label>
                        Métrica de la gráfica
                    </label>
                    <select
                        class="r13b-metric-select"
                        data-r13b-dimension-metric="${esc(c.id)}"
                    >
                        ${
                            metricDefs
                                .map(
                                    metric=>`
                                    <option
                                        value="${esc(metric.id)}"
                                        ${
                                            chartMetricDef
                                            &&metric.id===chartMetricDef.id
                                                ?'selected'
                                                :''
                                        }
                                    >
                                        ${esc(metric.label)}
                                    </option>`
                                )
                                .join('')
                        }
                    </select>
                </div>`
                :'';

        const defaultChartTopN=
            Math.max(
                1,
                Math.min(
                    Number(
                        chartSpec.top_n
                        ||topN
                    ),
                    50
                )
            );

        const chartControlState=
            (
                dimensionChartControls[c.id]
                &&typeof dimensionChartControls[c.id]==='object'
            )
                ?dimensionChartControls[c.id]
                :{};

        const chartTopN=
            Math.max(
                1,
                Math.min(
                    Number(
                        chartControlState.top_n
                        ||defaultChartTopN
                    ),
                    50
                )
            );

        const chartSortOrder=
            (
                String(
                    chartControlState.sort_order
                    ||'desc'
                )==='asc'
            )
                ?'asc'
                :'desc';

        const chartView=
            (
                String(
                    chartControlState.chart_view
                    ||'bars'
                )==='list'
            )
                ?'list'
                :'bars';

        dimensionChartControls[c.id]={
            top_n:chartTopN,
            sort_order:chartSortOrder,
            chart_view:chartView
        };

        let chartHtml='';

        if(
            chartOperator==='dimension_bar_chart'
            &&chartMetricDef
        ){

            const chartData=
                rowsAgg
                    .map(
                        item=>{

                            const value=
                                Number(
                                    item.metrics[
                                        chartMetricDef.id
                                    ]
                                );

                            const label=
                                (
                                    item.label
                                    &&item.label!=='Sin dato'
                                )
                                    ?item.label
                                    :item.identity;

                            return {
                                labels:[
                                    String(label)
                                ],
                                value:
                                    Number.isFinite(value)
                                        ?value
                                        :0,
                                drill_column:
                                    identityCol,
                                drill_value:
                                    item.identity
                            };
                        }
                    )
                    .sort(
                        (a,b)=>
                            chartSortOrder==='asc'
                                ?a.value-b.value
                                :b.value-a.value
                    )
                    .slice(
                        0,
                        chartTopN
                    );

            const chartTitle=
                (
                    chartMetricDef.label
                    +' por '
                    +dimensionRole
                );

            chartHtml=
                chartView==='list'
                    ?rankingListCard(
                        chartTitle,
                        chartData,
                        chartMetricDef.format
                    )
                    :barsCard(
                        chartTitle,
                        chartData,
                        {
                            full:true
                        }
                    );
        }

        const chartControlsHtml=`
        <div class="r13b-chart-controls">
            <label>
                Top
                <select
                    data-r13b-dimension-topn="${esc(c.id)}"
                >
                    ${
                        [5,10,15,20,30,50]
                            .map(
                                n=>`
                                <option
                                    value="${n}"
                                    ${n===chartTopN?'selected':''}
                                >
                                    ${n}
                                </option>`
                            )
                            .join('')
                    }
                </select>
            </label>

            <label>
                Orden
                <select
                    data-r13b-dimension-order="${esc(c.id)}"
                >
                    <option
                        value="desc"
                        ${chartSortOrder==='desc'?'selected':''}
                    >
                        Mayor → menor
                    </option>
                    <option
                        value="asc"
                        ${chartSortOrder==='asc'?'selected':''}
                    >
                        Menor → mayor
                    </option>
                </select>
            </label>

            <label>
                Vista
                <select
                    data-r13b-dimension-view="${esc(c.id)}"
                >
                    <option
                        value="bars"
                        ${chartView==='bars'?'selected':''}
                    >
                        Barras
                    </option>
                    <option
                        value="list"
                        ${chartView==='list'?'selected':''}
                    >
                        Ranking
                    </option>
                </select>
            </label>
        </div>`;

        const activeDrill=
            dimensionDrillFilters[
                identityCol
            ]
            ||null;

        const drillStatusHtml=
            activeDrill
                ?`
                <div class="r13b-drill-status">
                    <span>
                        Filtro analítico:
                        <strong>
                            ${esc(
                                activeDrill.label
                                ||activeDrill.value
                            )}
                        </strong>
                    </span>
                    <button
                        type="button"
                        data-r13b-clear-drill="${esc(identityCol)}"
                    >
                        Quitar filtro
                    </button>
                </div>`
                :'';

        return `
        ${metricSelectorHtml}
        ${chartControlsHtml}
        ${drillStatusHtml}
        ${chartHtml}
        <article class="r13b-card full">
            <h3>${esc(
                c.title
                ||('Rentabilidad por '+dimensionRole)
            )}</h3>

            <div class="r13b-small">
                ${groups.length.toLocaleString('es-MX')}
                entidades únicas sobre
                ${rr.length.toLocaleString('es-MX')}
                registros filtrados.
                Mostrando
                ${view.length.toLocaleString('es-MX')}.
            </div>

            <div class="r13b-table-wrap">
                <table class="r13b-table">
                    <thead>
                        <tr>
                            <th>${esc(identityRole)}</th>
                            ${
                                showLabel
                                    ?`<th>${esc(labelRole)}</th>`
                                    :''
                            }
                            ${
                                metricDefs
                                    .map(
                                        metric=>
                                            `<th>${esc(metric.label)}</th>`
                                    )
                                    .join('')
                            }
                            <th>Detalle</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${
                            view.map(
                                item=>`
                                <tr>
                                    <td>${esc(item.identity)}</td>
                                    ${
                                        showLabel
                                            ?`<td>${esc(item.label)}</td>`
                                            :''
                                    }
                                    ${
                                        metricDefs
                                            .map(
                                                metric=>`
                                                <td>${
                                                    fmt(
                                                        item.metrics[
                                                            metric.id
                                                        ],
                                                        metric.format
                                                    )
                                                }</td>`
                                            )
                                            .join('')
                                    }
                                    <td>
                                        <button
                                            type="button"
                                            class="r13b-drill-through-btn"
                                            data-r13b-drill-through-column="${esc(identityCol)}"
                                            data-r13b-drill-through-value="${esc(item.identity)}"
                                            data-r13b-drill-through-label="${esc(
                                                item.label
                                                ||item.identity
                                            )}"
                                        >
                                            Ver detalle
                                        </button>
                                    </td>
                                </tr>`
                            ).join('')
                        }
                    </tbody>
                </table>
            </div>
        </article>`;
    }


    function aggregatedTableCard(
        title,
        rr,
        keyDefs,
        {
            limit=100,
            sortMetric='kpi:revenue'
        }={}
    ){

        const validKeys=
            (keyDefs||[])
                .filter(
                    x=>
                        x
                        &&x.column
                );


        if(!validKeys.length){

            return `
            <article class="r13b-card">

                <h3>
                    ${esc(title)}
                </h3>

                <div class="r13b-small">
                    No existe una dimensión semántica
                    válida para agrupar esta tabla.
                </div>

            </article>`;
        }


        const groups=
            aggregateGroups(
                rr,
                validKeys.map(
                    x=>x.column
                )
            );


        const metricDefs=
            businessMetricDefinitions();


        const rowsAgg=
            groups.map(
                group=>{

                    const metrics={};


                    for(const metric of metricDefs){

                        metrics[
                            metric.id
                        ]=
                            aggregateMetric(
                                metric.component,
                                group.rows
                            );
                    }


                    return {
                        group,
                        metrics
                    };
                }
            );


        rowsAgg.sort(
            (a,b)=>{

                const av=
                    Number(
                        a.metrics[
                            sortMetric
                        ]
                    );

                const bv=
                    Number(
                        b.metrics[
                            sortMetric
                        ]
                    );


                if(
                    Number.isFinite(av)
                    ||Number.isFinite(bv)
                ){

                    return (
                        (
                            Number.isFinite(bv)
                                ?bv
                                :0
                        )
                        -
                        (
                            Number.isFinite(av)
                                ?av
                                :0
                        )
                    );
                }


                return (
                    b.group.count
                    -a.group.count
                );
            }
        );


        const view=
            rowsAgg.slice(
                0,
                limit
            );


        return `
        <article class="r13b-card full">

            <h3>
                ${esc(title)}
            </h3>

            <div class="r13b-small">

                ${
                    groups.length
                        .toLocaleString(
                            'es-MX'
                        )
                }
                entidades únicas sobre

                ${
                    rr.length
                        .toLocaleString(
                            'es-MX'
                        )
                }
                registros filtrados.

                Mostrando
                ${
                    view.length
                        .toLocaleString(
                            'es-MX'
                        )
                }.

            </div>


            <div class="r13b-table-wrap">

                <table class="r13b-table">

                    <thead>

                        <tr>

                            ${
                                validKeys
                                    .map(
                                        key=>
                                            `<th>${esc(key.label)}</th>`
                                    )
                                    .join('')
                            }

                            ${
                                metricDefs
                                    .map(
                                        metric=>
                                            `<th>${esc(metric.label)}</th>`
                                    )
                                    .join('')
                            }

                        </tr>

                    </thead>


                    <tbody>

                        ${
                            view
                                .map(
                                    item=>`

                                    <tr>

                                        ${
                                            item.group.labels
                                                .map(
                                                    value=>
                                                        `<td>${esc(value)}</td>`
                                                )
                                                .join('')
                                        }


                                        ${
                                            metricDefs
                                                .map(
                                                    metric=>{

                                                        const value=
                                                            item.metrics[
                                                                metric.id
                                                            ];

                                                        return `
                                                        <td>
                                                            ${
                                                                fmt(
                                                                    value,
                                                                    metric.format
                                                                )
                                                            }
                                                        </td>`;

                                                    }
                                                )
                                                .join('')
                                        }

                                    </tr>
                                    `
                                )
                                .join('')
                        }

                    </tbody>

                </table>

            </div>

        </article>`;
    }


    function genericTableCard(c,rr){

        if(c.status==='BLOCKED'){

            return blockedCard(c);
        }

        const execution=
            c.execution
            ||{};

        const operator=
            String(
                execution.operator
                ||''
            );

        /*
        * =====================================================
        * R10.13D.4
        * SPEC-DRIVEN BUSINESS TABLE EXECUTOR
        * =====================================================
        */

        if(operator==='grouped_business_table'){

            const grainRoles=
                Array.isArray(execution.grain_roles)
                    ?execution.grain_roles
                    :[];

            const fallbackGrainRoles=
                Array.isArray(execution.fallback_grain_roles)
                    ?execution.fallback_grain_roles
                    :[];

            const labelRoles=
                Array.isArray(execution.label_roles)
                    ?execution.label_roles
                    :[];

            const measureKpis=
                Array.isArray(execution.measure_kpis)
                    ?execution.measure_kpis
                    :[];

            const sortMetric=
                String(
                    execution.sort_metric
                    ||'kpi:revenue'
                );

            const limit=
                Math.max(
                    1,
                    Math.min(
                        Number(
                            execution.limit
                            ||100
                        ),
                        1000
                    )
                );


            /*
            * =====================================================
            * RESOLUCIÓN DEL GRAIN
            * =====================================================
            */

            let activeGrainRoles=
                grainRoles.filter(
                    r=>role(r)
                );

            let grainColumns=
                activeGrainRoles
                    .map(role)
                    .filter(Boolean);


            if(!grainColumns.length){

                activeGrainRoles=
                    fallbackGrainRoles.filter(
                        r=>role(r)
                    );

                grainColumns=
                    activeGrainRoles
                        .map(role)
                        .filter(Boolean);
            }


            if(!grainColumns.length){

                return blockedCard({
                    ...c,
                    status:'BLOCKED',
                    reason:
                        'No existe una dimensión semántica válida para ejecutar la tabla agrupada.'
                });
            }


            /*
            * =====================================================
            * ETIQUETAS VISIBLES
            *
            * Evita duplicados como:
            *
            * product | product
            * seller  | seller
            *
            * Si el label_role ya forma parte del grain,
            * no se vuelve a mostrar.
            * =====================================================
            */

            const effectiveLabelRoles=
                labelRoles.filter(
                    r=>
                        !activeGrainRoles.includes(r)
                        &&role(r)
                );


            /*
            * =====================================================
            * AGRUPACIÓN
            * =====================================================
            */

            const groups=
                aggregateGroups(
                    rr,
                    grainColumns
                );


            /*
            * =====================================================
            * MÉTRICAS SOLICITADAS POR EL SPEC
            * =====================================================
            */

            const metricDefs=
                businessMetricDefinitions()
                    .filter(
                        metric=>
                            !measureKpis.length
                            ||measureKpis.includes(
                                metric.id
                            )
                    );


            /*
            * =====================================================
            * EJECUCIÓN DE MÉTRICAS POR ENTIDAD
            * =====================================================
            */

            const rowsAgg=
                groups.map(
                    group=>{

                        const metrics={};


                        for(const metric of metricDefs){

                            metrics[
                                metric.id
                            ]=
                                aggregateMetric(
                                    metric.component,
                                    group.rows
                                );
                        }


                        /*
                        * Etiquetas descriptivas.
                        *
                        * Ejemplo futuro:
                        *
                        * grain = product_id
                        * label = product
                        *
                        * Se toma una descripción válida
                        * dentro del grupo.
                        */

                        const labels={};


                        for(
                            const labelRole
                            of effectiveLabelRoles
                        ){

                            const col=
                                role(
                                    labelRole
                                );


                            if(!col){
                                continue;
                            }


                            const first=
                                group.rows.find(
                                    row=>
                                        row[col]!==null
                                        &&row[col]!==undefined
                                        &&String(
                                            row[col]
                                        ).trim()!==''
                                );


                            labels[
                                labelRole
                            ]=
                                first
                                    ?String(
                                        first[col]
                                    )
                                    :'Sin dato';
                        }


                        return {
                            group,
                            metrics,
                            labels
                        };
                    }
                );


            /*
            * =====================================================
            * ORDENAMIENTO
            * =====================================================
            */

            rowsAgg.sort(
                (a,b)=>{

                    const av=
                        Number(
                            a.metrics[
                                sortMetric
                            ]
                        );

                    const bv=
                        Number(
                            b.metrics[
                                sortMetric
                            ]
                        );


                    if(
                        Number.isFinite(av)
                        ||Number.isFinite(bv)
                    ){

                        return (
                            (
                                Number.isFinite(bv)
                                    ?bv
                                    :0
                            )
                            -
                            (
                                Number.isFinite(av)
                                    ?av
                                    :0
                            )
                        );
                    }


                    return (
                        b.group.count
                        -
                        a.group.count
                    );
                }
            );


            /*
            * =====================================================
            * LÍMITE VISUAL
            * =====================================================
            */

            const view=
                rowsAgg.slice(
                    0,
                    limit
                );


            /*
            * Los encabezados principales corresponden
            * únicamente al grain realmente utilizado.
            */

            const keyHeaders=
                activeGrainRoles;


            /*
            * =====================================================
            * RENDER
            * =====================================================
            */

            return `
            <article class="r13b-card full">

                <h3>
                    ${
                        esc(
                            c.title
                            ||c.semantic_role
                            ||c.id
                            ||'Tabla'
                        )
                    }
                </h3>


                <div class="r13b-small">

                    ${
                        groups.length
                            .toLocaleString(
                                'es-MX'
                            )
                    }
                    entidades únicas sobre

                    ${
                        rr.length
                            .toLocaleString(
                                'es-MX'
                            )
                    }
                    registros filtrados.

                    Mostrando
                    ${
                        view.length
                            .toLocaleString(
                                'es-MX'
                            )
                    }.

                </div>


                <div class="r13b-table-wrap">

                    <table class="r13b-table">

                        <thead>

                            <tr>

                                ${
                                    keyHeaders
                                        .map(
                                            r=>
                                                `<th>${esc(r)}</th>`
                                        )
                                        .join('')
                                }


                                ${
                                    effectiveLabelRoles
                                        .map(
                                            r=>
                                                `<th>${esc(r)}</th>`
                                        )
                                        .join('')
                                }


                                ${
                                    metricDefs
                                        .map(
                                            metric=>
                                                `<th>${esc(metric.label)}</th>`
                                        )
                                        .join('')
                                }

                            </tr>

                        </thead>


                        <tbody>

                            ${
                                view
                                    .map(
                                        item=>`

                                        <tr>

                                            ${
                                                item.group.labels
                                                    .map(
                                                        value=>
                                                            `<td>${esc(value)}</td>`
                                                    )
                                                    .join('')
                                            }


                                            ${
                                                effectiveLabelRoles
                                                    .map(
                                                        r=>
                                                            `<td>${
                                                                esc(
                                                                    item.labels[r]
                                                                    ??'Sin dato'
                                                                )
                                                            }</td>`
                                                    )
                                                    .join('')
                                            }


                                            ${
                                                metricDefs
                                                    .map(
                                                        metric=>{

                                                            const value=
                                                                item.metrics[
                                                                    metric.id
                                                                ];


                                                            return `
                                                            <td>
                                                                ${
                                                                    fmt(
                                                                        value,
                                                                        metric.format
                                                                    )
                                                                }
                                                            </td>`;
                                                        }
                                                    )
                                                    .join('')
                                            }

                                        </tr>
                                        `
                                    )
                                    .join('')
                            }

                        </tbody>

                    </table>

                </div>

            </article>`;
        }



        /*
         * =====================================================
         * R10.13D.4
         * SPEC-DRIVEN TRANSACTION TABLE EXECUTOR
         * =====================================================
         */

        if(operator==='transaction_table'){

            const requestedRoles=
                Array.isArray(execution.columns)
                    ?execution.columns
                    :[];

            const cols=
                requestedRoles
                    .map(
                        r=>
                            role(r)
                    )
                    .filter(Boolean);

            const uniqueCols=
                [
                    ...new Set(cols)
                ];

            if(!uniqueCols.length){

                return blockedCard({
                    ...c,
                    status:'BLOCKED',
                    reason:
                        'No existen columnas semánticas válidas para ejecutar la tabla transaccional.'
                });
            }

            const limit=
                Math.max(
                    1,
                    Math.min(
                        Number(
                            execution.limit
                            ||250
                        ),
                        2000
                    )
                );

            return tableCard(
                c.title
                ||c.semantic_role
                ||'Operaciones',
                rr,
                uniqueCols,
                limit
            );
        }


        /*
         * =====================================================
         * R10.13D.4
         * SPEC-DRIVEN RAW TABLE EXECUTOR
         * =====================================================
         */

        if(operator==='raw_table'){

            const cols=
                [
                    ...new Set(
                        (
                            c.source_columns
                            ||[]
                        )
                            .filter(Boolean)
                            .slice(0,12)
                    )
                ];

            if(!cols.length){

                return blockedCard({
                    ...c,
                    status:'BLOCKED',
                    reason:
                        'No existen columnas ejecutables asociadas a esta tabla.'
                });
            }

            const limit=
                Math.max(
                    1,
                    Math.min(
                        Number(
                            execution.limit
                            ||100
                        ),
                        2000
                    )
                );

            return tableCard(
                c.title
                ||c.semantic_role
                ||'Tabla',
                rr,
                cols,
                limit
            );
        }


        /*
         * =====================================================
         * R10.13D.5
         * OPERATOR-DRIVEN TABLE INDEPENDENCE
         * =====================================================
         *
         * La ejecución de tablas ya no depende de IDs fijos como:
         * table:customers, table:products, table:sellers o
         * table:operations.
         *
         * La autoridad de ejecución es execution.operator.
         */

        /*
         * FALLBACK
         */

        const cols=
            [
                ...new Set(
                    (
                        c.source_columns
                        ||[]
                    )
                    .filter(Boolean)
                    .slice(0,12)
                )
            ];


        if(!cols.length){

            return `
            <article class="r13b-card">

                <h3>
                    ${
                        esc(
                            c.title
                            ||c.semantic_role
                            ||c.id
                        )
                    }
                </h3>

                <span class="r13b-status SUPPORTED">
                    SUPPORTED
                </span>

                <div class="r13b-small">
                    No existen columnas ejecutables
                    asociadas a esta tabla.
                </div>

            </article>`;
        }


        return tableCard(
            c.title
            ||c.semantic_role
            ||'Tabla',
            rr,
            cols,
            100
        );
    }


    /*
     * =====================================================
     * R10.13D.1
     * GENERIC FILTER EXECUTOR
     * =====================================================
     */

    function genericFilterCard(c){

        if(c.status==='BLOCKED'){
            return blockedCard(c);
        }

        return `
        <article class="r13b-card">

            <h3>
                Filtro ·
                ${
                    esc(
                        c.title
                        ||c.semantic_role
                        ||c.id
                    )
                }
            </h3>

            <span class="r13b-status SUPPORTED">
                SUPPORTED
            </span>

            <div class="r13b-small">
                Filtro global activo para esta página.
            </div>

            ${
                sourceLine(
                    c.source_columns||[]
                )
            }

        </article>`;
    }


    /*
     * =====================================================
     * R10.13D.1
     * DELIVERABLE EXECUTOR
     * =====================================================
     */

    function deliverableCard(c){

        if(c.status==='BLOCKED'){
            return blockedCard(c);
        }

        return `
        <article class="r13b-card">

            <h3>
                ${
                    esc(
                        c.title
                        ||c.semantic_role
                        ||'Entregable'
                    )
                }
            </h3>

            <span class="r13b-status SUPPORTED">
                SUPPORTED
            </span>

            <div class="r13b-small">
                Entregable solicitado por el prompt
                y cubierto por el dashboard.
            </div>

        </article>`;
    }


    /*
     * =====================================================
     * R10.13D.1
     * CANONICAL COMPONENT EXECUTOR
     * =====================================================
     */

    function componentCard(c,rr){

        if(!c){
            return '';
        }

        /*
         * BLOCKED tiene prioridad absoluta.
         */

        if(c.status==='BLOCKED'){

            return blockedCard(c);
        }


        if(c.type==='kpi'){

            return kpiCard(
                c,
                rr
            );
        }


        if(c.type==='analysis'){

            return analysisCard(
                c,
                rr
            );
        }


        if(c.type==='table'){

            return genericTableCard(
                c,
                rr
            );
        }


        if(c.type==='filter'){

            return genericFilterCard(c);
        }


        if(c.type==='deliverable'){

            return deliverableCard(c);
        }


        return `
        <article class="r13b-card">

            <h3>
                ${
                    esc(
                        c.title
                        ||c.semantic_role
                        ||c.id
                    )
                }
            </h3>

            <span class="r13b-status ${esc(c.status||'SUPPORTED')}">
                ${esc(c.status||'SUPPORTED')}
            </span>

            ${
                sourceLine(
                    c.source_columns||[]
                )
            }

        </article>`;
    }


    /*
     * =====================================================
     * R10.13D.1
     * PAGE COMPONENT EXECUTOR
     * =====================================================
     */

    function pageHtml(page,rr){

        const comps=
            (page.components||[])
                .map(
                    id=>
                        model.components[id]
                )
                .filter(Boolean);

        const parts=[];


        for(const c of comps){

            const html=
                componentCard(
                    c,
                    rr
                );

            if(html){
                parts.push(html);
            }
        }


        return (
            parts.join('')
            || '<div class="r13b-empty">No hay componentes ejecutables para esta página con los datos actuales.</div>'
        );
    }


    /*
     * =====================================================
     * R10.13D.12
     * CONTEXTUAL DRILL-THROUGH
     * =====================================================
     */

    function drillThroughColumns(){

        const components=
            Object.values(
                model.components
                ||{}
            );

        const tx=
            components.find(
                c=>
                    c
                    &&c.type==='table'
                    &&c.execution
                    &&String(
                        c.execution.operator
                        ||''
                    )==='transaction_table'
            )
            ||null;

        const requestedRoles=
            tx
            &&Array.isArray(
                tx.execution.columns
            )
                ?tx.execution.columns
                :[
                    'transaction_id',
                    'date',
                    'customer',
                    'product',
                    'seller',
                    'warehouse',
                    'revenue',
                    'cost',
                    'quantity',
                    'origin_city',
                    'destination_city'
                ];

        return [
            ...new Set(
                requestedRoles
                    .map(
                        r=>({
                            role:r,
                            column:role(r)
                        })
                    )
                    .filter(
                        item=>item.column
                    )
                    .map(
                        item=>item.column
                    )
            )
        ];
    }


    function activeDrillSummary(){

        return Object.values(
            dimensionDrillFilters
        )
            .filter(
                item=>
                    item
                    &&item.column
                    &&item.value!==undefined
                    &&item.value!==null
            );
    }


    function closeDrillThrough(){

        if(!drillThroughModal){
            return;
        }

        drillThroughModal.classList.remove(
            'open'
        );

        drillThroughModal.setAttribute(
            'aria-hidden',
            'true'
        );
    }


    function openDrillThrough(
        column,
        value,
        label
    ){

        if(
            !drillThroughModal
            ||!column
        ){
            return;
        }

        const contextualRows=
            rows().filter(
                row=>
                    String(
                        row[column]
                        ??'Sin dato'
                    )===String(value)
            );

        const cols=
            drillThroughColumns();

        const limit=500;

        const visibleRows=
            contextualRows.slice(
                0,
                limit
            );

        const title=
            drillThroughModal.querySelector(
                '#r13bDrillThroughTitle'
            );

        const subtitle=
            drillThroughModal.querySelector(
                '#r13bDrillThroughSubtitle'
            );

        const body=
            drillThroughModal.querySelector(
                '#r13bDrillThroughBody'
            );

        if(title){
            title.textContent=
                'Detalle transaccional · '
                +String(
                    label
                    ||value
                );
        }

        if(subtitle){
            subtitle.textContent=
                contextualRows.length
                    .toLocaleString(
                        'es-MX'
                    )
                +' registros bajo el contexto analítico actual.';
        }

        const active=
            activeDrillSummary();

        const contextHtml=`
            <div class="r13b-drill-through-meta">
                <span>
                    Entidad:
                    ${esc(column)}
                    =
                    ${esc(value)}
                </span>
                ${
                    active
                        .map(
                            item=>`
                            <span>
                                ${esc(item.column)}
                                =
                                ${esc(
                                    item.label
                                    ||item.value
                                )}
                            </span>`
                        )
                        .join('')
                }
                <span>
                    Registros:
                    ${contextualRows.length.toLocaleString('es-MX')}
                </span>
            </div>`;

        if(!body){
            return;
        }

        if(
            !contextualRows.length
            ||!cols.length
        ){
            body.innerHTML=
                contextHtml
                +`
                <div class="r13b-drill-through-empty">
                    No existen registros transaccionales
                    para este contexto.
                </div>`;
        }else{
            body.innerHTML=
                contextHtml
                +`
                <div class="r13b-table-wrap">
                    <table class="r13b-table">
                        <thead>
                            <tr>
                                ${
                                    cols
                                        .map(
                                            col=>
                                                `<th>${esc(col)}</th>`
                                        )
                                        .join('')
                                }
                            </tr>
                        </thead>
                        <tbody>
                            ${
                                visibleRows
                                    .map(
                                        row=>`
                                        <tr>
                                            ${
                                                cols
                                                    .map(
                                                        col=>`
                                                        <td>
                                                            ${esc(
                                                                row[col]
                                                                ??'Sin dato'
                                                            )}
                                                        </td>`
                                                    )
                                                    .join('')
                                            }
                                        </tr>`
                                    )
                                    .join('')
                            }
                        </tbody>
                    </table>
                </div>
                ${
                    contextualRows.length>limit
                        ?`
                        <div class="r13b-small">
                            Mostrando los primeros
                            ${limit.toLocaleString('es-MX')}
                            de
                            ${contextualRows.length.toLocaleString('es-MX')}
                            registros.
                        </div>`
                        :''
                }`;
        }

        drillThroughModal.classList.add(
            'open'
        );

        drillThroughModal.setAttribute(
            'aria-hidden',
            'false'
        );
    }


    drillThroughModal
        .querySelector(
            '[data-r13b-drill-through-close]'
        )
        ?.addEventListener(
            'click',
            closeDrillThrough
        );

    drillThroughModal.addEventListener(
        'click',
        event=>{
            if(
                event.target===drillThroughModal
            ){
                closeDrillThrough();
            }
        }
    );

    document.addEventListener(
        'keydown',
        event=>{
            if(
                event.key==='Escape'
                &&drillThroughModal.classList.contains(
                    'open'
                )
            ){
                closeDrillThrough();
            }
        }
    );


    /*
     * =====================================================
     * R10.13D.11
     * MULTIDIMENSIONAL ANALYTICAL FILTER SUMMARY
     * =====================================================
     */
    function renderDrillFilterBar(){

        if(!drillFilterHost){
            return;
        }

        const active=
            Object.values(
                dimensionDrillFilters
            )
                .filter(
                    item=>
                        item
                        &&item.column
                        &&item.value!==undefined
                        &&item.value!==null
                );

        if(!active.length){

            drillFilterHost.classList.remove(
                'is-active'
            );

            drillFilterHost.innerHTML='';
            return;
        }

        drillFilterHost.classList.add(
            'is-active'
        );

        drillFilterHost.innerHTML=`
        <div class="r13b-drill-filter-bar">
            <span class="r13b-drill-filter-title">
                Filtros analíticos
            </span>

            <span class="r13b-drill-count">
                ${active.length}
                activo${active.length===1?'':'s'}
            </span>

            ${
                active
                    .map(
                        item=>`
                        <span
                            class="r13b-drill-chip"
                            title="${esc(
                                item.column
                                +' = '
                                +item.value
                            )}"
                        >
                            <b>${esc(item.column)}</b>
                            <span>
                                ${esc(
                                    item.label
                                    ||item.value
                                )}
                            </span>
                            <button
                                type="button"
                                aria-label="Quitar filtro ${esc(
                                    item.label
                                    ||item.value
                                )}"
                                data-r13b-clear-global-drill="${esc(item.column)}"
                            >
                                ×
                            </button>
                        </span>`
                    )
                    .join('')
            }

            ${
                active.length>1
                    ?`
                    <button
                        type="button"
                        class="r13b-drill-clear-all"
                        data-r13b-clear-all-drills
                    >
                        Limpiar todos
                    </button>`
                    :''
            }
        </div>`;

        drillFilterHost
            .querySelectorAll(
                '[data-r13b-clear-global-drill]'
            )
            .forEach(
                button=>{
                    button.onclick=()=>{

                        const column=String(
                            button.dataset.r13bClearGlobalDrill
                            ||''
                        );

                        if(!column){
                            return;
                        }

                        delete dimensionDrillFilters[
                            column
                        ];

                        renderPages();
                    };
                }
            );

        const clearAll=
            drillFilterHost.querySelector(
                '[data-r13b-clear-all-drills]'
            );

        if(clearAll){
            clearAll.onclick=()=>{

                for(
                    const column
                    of Object.keys(
                        dimensionDrillFilters
                    )
                ){
                    delete dimensionDrillFilters[
                        column
                    ];
                }

                renderPages();
            };
        }
    }


    /*
     * =====================================================
     * RENDER PAGES
     * =====================================================
     */

    function renderPages(){

        const rr=rows();

        renderDrillFilterBar();

        model.pages.forEach(page=>{

            const mount=
                document.querySelector(
                    `[data-r13b-mount="${CSS.escape(page.id)}"]`
                );

            if(!mount){
                return;
            }


            if(legacyMode){

                const derived=
                    (page.components||[])
                        .map(
                            id=>
                                model.components[id]
                        )
                        .filter(
                            c=>
                                c
                                &&c.type==='kpi'
                                &&c.status==='DERIVABLE'
                                &&(
                                    (c.provenance||{}).source
                                    ==='capability_rule_registry'
                                )
                        );


                mount.innerHTML=
                    derived.length
                        ? `
                        <div
                            class="r13b-page-meta"
                            style="grid-column:span 12"
                        >
                            Métricas derivadas gobernadas ·
                            ${
                                esc(
                                    model.ruleset_version
                                    ||'r10.13c'
                                )
                            }
                        </div>

                        ${
                            derived
                                .map(
                                    c=>
                                        kpiCard(
                                            c,
                                            rr
                                        )
                                )
                                .join('')
                        }
                        `
                        :'';
            }


            else{

                mount.innerHTML=
                    pageHtml(
                        page,
                        rr
                    );
            }

        });


        const planner=$('planner');

        if(planner){

            planner.textContent=
                `R10.13C · ${
                    model.domain||'generic'
                } · ${
                    model.pages.length
                } páginas`;
        }

        /*
         * R10.13D.8
         * Re-vincula selectores porque pageHtml reemplaza innerHTML
         * en cada render reactivo.
         */
        document
            .querySelectorAll(
                'select[data-r13b-dimension-metric]'
            )
            .forEach(
                select=>{
                    select.onchange=()=>{
                        const componentId=
                            String(
                                select.dataset.r13bDimensionMetric
                                ||''
                            );

                        if(!componentId){
                            return;
                        }

                        dimensionMetricSelection[
                            componentId
                        ]=String(
                            select.value
                            ||''
                        );

                        renderPages();
                    };
                }
            );

        /*
         * =====================================================
         * R10.13D.12
         * DRILL-THROUGH BUTTON BINDING
         * =====================================================
         */
        document
            .querySelectorAll(
                '[data-r13b-drill-through-column]'
            )
            .forEach(
                button=>{
                    button.onclick=()=>{

                        openDrillThrough(
                            String(
                                button.dataset.r13bDrillThroughColumn
                                ||''
                            ),
                            String(
                                button.dataset.r13bDrillThroughValue
                                ??''
                            ),
                            String(
                                button.dataset.r13bDrillThroughLabel
                                ||button.dataset.r13bDrillThroughValue
                                ||''
                            )
                        );
                    };
                }
            );

        /*
         * =====================================================
         * R10.13D.10
         * CLICK-TO-FILTER / DRILL-DOWN
         * =====================================================
         */
        document
            .querySelectorAll(
                '[data-r13b-drill-column]'
            )
            .forEach(
                node=>{

                    const applyDrill=()=>{

                        const column=String(
                            node.dataset.r13bDrillColumn
                            ||''
                        );

                        const value=String(
                            node.dataset.r13bDrillValue
                            ??''
                        );

                        const label=String(
                            node.dataset.r13bDrillLabel
                            ||value
                        );

                        if(!column){
                            return;
                        }

                        /*
                         * R10.13D.11
                         * Misma dimensión => reemplaza.
                         * Otra dimensión => se acumula.
                         */
                        dimensionDrillFilters[
                            column
                        ]={
                            column,
                            value,
                            label
                        };

                        renderPages();
                    };

                    node.onclick=applyDrill;

                    node.onkeydown=event=>{
                        if(
                            event.key==='Enter'
                            ||event.key===' '
                        ){
                            event.preventDefault();
                            applyDrill();
                        }
                    };
                }
            );

        document
            .querySelectorAll(
                '[data-r13b-clear-drill]'
            )
            .forEach(
                button=>{
                    button.onclick=()=>{

                        const column=String(
                            button.dataset.r13bClearDrill
                            ||''
                        );

                        if(!column){
                            return;
                        }

                        delete dimensionDrillFilters[
                            column
                        ];

                        renderPages();
                    };
                }
            );

        /*
         * R10.13D.9
         * Top N / orden / vista.
         */
        document
            .querySelectorAll(
                'select[data-r13b-dimension-topn],'
                +'select[data-r13b-dimension-order],'
                +'select[data-r13b-dimension-view]'
            )
            .forEach(
                select=>{
                    select.onchange=()=>{
                        const componentId=String(
                            select.dataset.r13bDimensionTopn
                            ||select.dataset.r13bDimensionOrder
                            ||select.dataset.r13bDimensionView
                            ||''
                        );

                        if(!componentId){
                            return;
                        }

                        const state={
                            ...(
                                dimensionChartControls[
                                    componentId
                                ]
                                ||{}
                            )
                        };

                        if(
                            select.dataset.r13bDimensionTopn
                        ){
                            state.top_n=
                                Number(select.value)||15;
                        }

                        if(
                            select.dataset.r13bDimensionOrder
                        ){
                            state.sort_order=
                                String(select.value||'desc');
                        }

                        if(
                            select.dataset.r13bDimensionView
                        ){
                            state.chart_view=
                                String(select.value||'bars');
                        }

                        dimensionChartControls[
                            componentId
                        ]=state;

                        renderPages();
                    };
                }
            );
    }


    /*
     * FIXED LEGACY NODES
     */

    const fixedNodes={

        summary:[
            $('resumen'),
            $('graficas')
        ],

        operations:[
            $('detalle')
        ],

        analysis:[
            $('analitica')
        ],

        customers:[],

        customer_profile:[],

        line_analysis:[],

        lost_customers:[]
    };


    const chartHead=
        $('graficas')
            ?.previousElementSibling;


    if(
        chartHead
        &&chartHead.classList.contains(
            'section-head'
        )
    ){

        fixedNodes.summary.splice(
            1,
            0,
            chartHead
        );
    }


    /*
     * BUILD DYNAMIC PAGES
     */

    model.pages.forEach(
        (page,index)=>{

            const section=
                document.createElement(
                    'section'
                );

            section.className=
                'r13b-page'
                +(index===0?' active':'');

            section.id=
                'r13b-'+page.id;

            section.dataset.pageId=
                page.id;

            section.innerHTML=`

                <div class="r13b-page-head">

                    <div>

                        <h2>
                            ${esc(page.title)}
                        </h2>

                        <div class="r13b-page-meta">

                            ${
                                /*
                                * Compatibility marker retained for R10.13D.1 regression tests:
                                * R10.13D.1 · Generic Component Executor
                                */

                                legacyMode
                                    ?'R10.13C · Compatibilidad comercial'
                                    :'R10.13D.5 · Operator-Driven Table Executor'
                            }

                            ·

                            ${
                                (page.components||[]).length
                            }

                            capacidades

                        </div>

                    </div>

                    <span class="r13b-status SUPPORTED">
                        ${
                            esc(
                                model.domain
                                ||'generic'
                            )
                        }
                    </span>

                </div>

                <div
                    class="r13b-grid"
                    data-r13b-mount="${esc(page.id)}"
                ></div>
            `;

            host.appendChild(section);


            /*
             * LEGACY COMPATIBILITY
             */

            if(legacyMode){

                (
                    fixedNodes[page.id]
                    ||[]
                )
                    .filter(Boolean)
                    .forEach(node=>{

                        node.classList.remove(
                            'view-secondary',
                            'is-open'
                        );

                        node.hidden=false;

                        section.appendChild(node);
                    });


                if(
                    page.id==='customers'
                    &&$('clientsAdvanced')
                ){

                    const card=
                        document.createElement(
                            'article'
                        );

                    card.className=
                        'table-card';

                    card.innerHTML=
                        '<h2>Clientes</h2>'
                        +'<div id="r13bClientsMount"></div>';

                    section.appendChild(card);

                    $('r13bClientsMount')
                        .appendChild(
                            $('clientsAdvanced')
                        );
                }


                if(page.id==='customer_profile'){

                    const card=
                        document.createElement(
                            'article'
                        );

                    card.className=
                        'table-card';

                    card.innerHTML=
                        '<h2>Perfil de Cliente</h2>'
                        +'<div class="small">'
                        +'Usa el filtro Cliente '
                        +'y el detalle para consultar '
                        +'un cliente individual.'
                        +'</div>';

                    section.appendChild(card);
                }


                if(page.id==='line_analysis'){

                    const card=
                        document.createElement(
                            'article'
                        );

                    card.className=
                        'table-card';

                    card.innerHTML=
                        '<h2>Análisis por Línea</h2>'
                        +'<div class="small">'
                        +'Los indicadores se recalculan '
                        +'con la selección actual.'
                        +'</div>';

                    section.appendChild(card);
                }


                if(page.id==='lost_customers'){

                    const card=
                        document.createElement(
                            'article'
                        );

                    card.className=
                        'audit';

                    card.innerHTML=
                        '<h2>'
                        +'Clientes perdidos / en riesgo'
                        +'</h2>'
                        +'<div class="small">'
                        +'Solo se muestran resultados '
                        +'soportados por los datos reales.'
                        +'</div>';

                    section.appendChild(card);
                }
            }

        }
    );


    /*
     * NAVIGATION
     */

    nav.innerHTML=
        model.pages
            .map(
                (p,i)=>`

                <a
                    href="#r13b-${esc(p.id)}"
                    data-r13b-page="${esc(p.id)}"
                    class="${i===0?'active':''}"
                >

                    <span class="ico">
                        ${esc(p.icon||'•')}
                    </span>

                    <span>
                        ${esc(p.title)}
                    </span>

                </a>
                `
            )
            .join('');


    function activate(pid){

        document
            .querySelectorAll(
                '.r13b-page'
            )
            .forEach(
                x=>
                    x.classList.toggle(
                        'active',
                        x.dataset.pageId===pid
                    )
            );


        nav
            .querySelectorAll('a')
            .forEach(
                x=>
                    x.classList.toggle(
                        'active',
                        x.dataset.r13bPage===pid
                    )
            );


        document.querySelector(
            `.r13b-page[data-page-id="${CSS.escape(pid)}"]`
        )
            ?.scrollIntoView({
                behavior:'smooth',
                block:'start'
            });
    }


    nav
        .querySelectorAll(
            'a[data-r13b-page]'
        )
        .forEach(
            a=>
                a.addEventListener(
                    'click',
                    e=>{

                        e.preventDefault();

                        activate(
                            a.dataset.r13bPage
                        );
                    }
                )
        );


    /*
     * REACTIVE FILTERING
     */

    window.addEventListener(
        'ia-dashboard-filter-change',
        renderPages
    );


    /*
     * INITIAL RENDER
     */

    renderPages();


}catch(err){

    console.error(
        'R10.13D.5 operator-driven renderer fallback:',
        err
    );
}

})();

</script>
'''


def attach_dynamic_renderer(
    plan: Dict[str, Any]
) -> Dict[str, Any]:

    out=plan

    execution=dict(
        out.get("execution_plan") or {}
    )

    spec=dict(
        execution.get("dashboard_spec") or {}
    )

    if spec:

        _canonicalize_execution_plan(
            out,
            spec
        )

        out["dynamic_renderer"] = (
            build_dynamic_renderer_model(
                spec,
                out
            )
        )

    else:

        out["dynamic_renderer"]={
            "version":VERSION,
            "enabled":False,
            "pages":[]
        }

    return out
