from pathlib import Path
from datetime import datetime
import shutil

ROOT=Path(__file__).resolve().parent
REPO=Path.cwd()
DYN=REPO/"IA_Local"/"scripts"/"dashboard_dynamic.py"
COMP=REPO/"IA_Local"/"scripts"/"enterprise_prompt_compiler.py"
ANA=REPO/"IA_Local"/"scripts"/"enterprise_analytics.py"
TESTS=REPO/"IA_Local"/"tests"/"test_bi_productivo.py"
ANALYZER=REPO/"IA_Local"/"scripts"/"analizador_universal.py"

for p in (DYN,COMP,TESTS,ANALYZER):
    if not p.exists(): raise SystemExit(f"ERROR: falta {p}. Debe estar aplicada R9.4.")

stamp=datetime.now().strftime("%Y%m%d_%H%M%S")
backup=REPO/"_backup_r9_5"/stamp; backup.mkdir(parents=True,exist_ok=True)
for p in (DYN,COMP,TESTS,ANALYZER):
    shutil.copy2(p,backup/p.name)
if ANA.exists(): shutil.copy2(ANA,backup/ANA.name)
shutil.copy2(ROOT/"enterprise_analytics.py",ANA)

def rep(text,old,new,label):
    if new in text: return text
    if old not in text: raise SystemExit(f"ERROR R9.5 [{label}]: patrón no encontrado")
    return text.replace(old,new,1)

c=COMP.read_text(encoding="utf-8")
old='''    out["prompt_compiler"] = {
        "version":"r9.4",
        "mode":"structured-enterprise",
        "source_of_truth": sheet or "BD",
        "kpi_count": len(kpis),
        "chart_count": len(charts),
        "filter_count": len(filters),
    }'''
new='''    from enterprise_analytics import build_advanced_analytics
    out["advanced"] = build_advanced_analytics(df)
    out["prompt_compiler"] = {
        "version":"r9.5",
        "mode":"structured-enterprise",
        "source_of_truth": sheet or "BD",
        "kpi_count": len(kpis),
        "chart_count": len(charts),
        "filter_count": len(filters),
        "advanced_renderer": True,
    }'''
c=rep(c,old,new,"compiler")
c=c.replace("R9.4 compiló métricas, filtros y visualizaciones explícitas desde el prompt.","R9.5 compiló métricas, filtros, visualizaciones y analítica avanzada desde el prompt.")
c=c.replace("enterprise-prompt-compiler-r9.4","enterprise-prompt-compiler-r9.5")
COMP.write_text(c,encoding="utf-8")

d=DYN.read_text(encoding="utf-8")
css='''.adv-grid{display:grid;grid-template-columns:repeat(12,1fr);gap:14px;margin-top:14px}
.adv-card{grid-column:span 6;background:#fff;border:1px solid var(--line);border-radius:var(--radius);padding:16px;box-shadow:var(--shadow);min-width:0}.adv-card.full{grid-column:span 12}
.findings{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:10px}.finding{border:1px solid #dbeaf0;background:#f8fcfd;border-radius:12px;padding:12px;font-size:12px;line-height:1.45}
.neg{color:#b52f2f;font-weight:700}.pos{color:#16833a;font-weight:700}.adv-table-wrap{overflow:auto;max-height:420px;border:1px solid #edf2f6;border-radius:11px}
.adv-table{width:100%;border-collapse:collapse;font-size:11px}.adv-table th{position:sticky;top:0;background:#f1f6f9;text-align:left}.adv-table th,.adv-table td{padding:8px 9px;border-bottom:1px solid #edf2f6;white-space:nowrap}
.bar.negative{background:linear-gradient(180deg,#ff8b86,var(--red))}.modal{position:fixed;inset:0;background:rgba(7,24,37,.42);display:none;align-items:center;justify-content:center;z-index:20;padding:20px}.modal.open{display:flex}
.modal-box{background:#fff;border-radius:18px;width:min(1050px,96vw);max-height:88vh;overflow:auto;padding:18px}.modal-head{display:flex;justify-content:space-between;align-items:center}.closebtn{border:0;background:#eef5f7;border-radius:9px;padding:8px 10px;cursor:pointer}
.searchbox,.datebox{background:#fff;border:1px solid var(--line);border-radius:12px;padding:8px 10px}.searchbox label,.datebox label{display:block;color:var(--muted);font-size:10px;font-weight:700;text-transform:uppercase;margin-bottom:5px}.searchbox input,.datebox input{border:0;outline:0}
@media(max-width:900px){.adv-card{grid-column:span 12}}'''
d=rep(d,"</style>",css+"\n</style>","css")

extra='''<section class="adv-grid" id="analitica">
<article class="adv-card full"><h2>Resumen Ejecutivo IA</h2><div class="findings" id="execFindings"></div></article>
<article class="adv-card"><h2>Clientes · Rentabilidad</h2><div id="clientsAdvanced"></div></article>
<article class="adv-card"><h2>Productos · Rentabilidad</h2><div id="productsAdvanced"></div></article>
<article class="adv-card full"><h2>Operaciones con Utilidad Negativa</h2><div id="negativeAdvanced"></div></article>
<article class="adv-card full"><h2>Rutas Origen → Destino</h2><div id="routesAdvanced"></div></article>
<article class="adv-card full"><h2>Validación Matemática</h2><div class="findings" id="validationAdvanced"></div></article>
</section>
<div class="modal" id="drillModal"><div class="modal-box"><div class="modal-head"><h2 id="drillTitle">Detalle</h2><button class="closebtn" id="drillClose">Cerrar</button></div><div id="drillBody"></div></div></div>'''
footer='<footer class="footer"><span><strong>PRIMOS & COUSINS</strong> · Innovando Juntos</span><span>Dashboard generado automáticamente por IA Empresarial Local</span></footer>'
d=rep(d,footer,extra+"\n"+footer,"html")

old="for(const f of(P.filters||[])){const box=document.createElement('div');box.className='filter';const vals=[...new Set(ALL.map(r=>r[f.column]).filter(v=>v!==null&&v!==undefined&&String(v)!==''))].sort((a,b)=>String(a).localeCompare(String(b),'es'));box.innerHTML=`<label>${esc(f.label||f.column)}</label><select data-col=\"${esc(f.column)}\"><option value=\"\">Todos</option>${vals.map(v=>`<option value=\"${esc(v)}\">${esc(v)}</option>`).join('')}</select>`;filterRoot.insertBefore(box,filterRoot.querySelector('.actions'))}\nfilterRoot.addEventListener('change',e=>{if(e.target.matches('select[data-col]')){selected[e.target.dataset.col]=e.target.value;render()}});$('clear').onclick=()=>{selected={};document.querySelectorAll('select[data-col]').forEach(s=>s.value='');render()};\nconst filtered=()=>ALL.filter(r=>Object.entries(selected).every(([c,v])=>!v||String(r[c])===v));"
new="let dateFrom='',dateTo='',clientSearch='',chartTop=20;\nfor(const f of(P.filters||[])){if(f.column==='Fecha')continue;const box=document.createElement('div');box.className='filter';const vals=[...new Set(ALL.map(r=>r[f.column]).filter(v=>v!==null&&v!==undefined&&String(v)!==''))].sort((a,b)=>String(a).localeCompare(String(b),'es'));const multi=['Zona','Categoria','Vendedor','ctrl_alm','Proveedor'].includes(f.column);box.innerHTML=`<label>${esc(f.label||f.column)}</label><select data-col=\"${esc(f.column)}\" ${multi?'multiple':''}>${multi?'':'<option value=\"\">Todos</option>'}${vals.map(v=>`<option value=\"${esc(v)}\">${esc(v)}</option>`).join('')}</select>`;filterRoot.insertBefore(box,filterRoot.querySelector('.actions'))}\nif(ALL.some(r=>r.Fecha)){const b=document.createElement('div');b.className='datebox';b.innerHTML='<label>Fecha desde / hasta</label><input id=\"dateFrom\" type=\"date\"> <input id=\"dateTo\" type=\"date\">';filterRoot.insertBefore(b,filterRoot.firstChild)}\nconst sb=document.createElement('div');sb.className='searchbox';sb.innerHTML='<label>Buscar cliente</label><input id=\"clientSearch\" placeholder=\"Nombre o código\">';filterRoot.insertBefore(sb,filterRoot.querySelector('.actions'));const tb=document.createElement('div');tb.className='filter';tb.innerHTML='<label>Top gráficas</label><select id=\"chartTop\"><option>10</option><option selected>20</option><option>50</option><option value=\"9999\">Todos</option></select>';filterRoot.insertBefore(tb,filterRoot.querySelector('.actions'));\nfilterRoot.addEventListener('change',e=>{if(e.target.matches('select[data-col]')){const col=e.target.dataset.col;selected[col]=e.target.multiple?[...e.target.selectedOptions].map(o=>o.value):e.target.value;render()}});document.getElementById('dateFrom')?.addEventListener('change',e=>{dateFrom=e.target.value;render()});document.getElementById('dateTo')?.addEventListener('change',e=>{dateTo=e.target.value;render()});document.getElementById('clientSearch').addEventListener('input',e=>{clientSearch=e.target.value.toLowerCase().trim();render()});document.getElementById('chartTop').addEventListener('change',e=>{chartTop=Number(e.target.value)||20;render()});$('clear').onclick=()=>{selected={};dateFrom='';dateTo='';clientSearch='';document.querySelectorAll('select[data-col]').forEach(s=>[...s.options].forEach(o=>o.selected=false));document.getElementById('dateFrom')&&(document.getElementById('dateFrom').value='');document.getElementById('dateTo')&&(document.getElementById('dateTo').value='');document.getElementById('clientSearch').value='';render()};\nconst filtered=()=>ALL.filter(r=>{for(const [c,v] of Object.entries(selected)){if(Array.isArray(v)){if(v.length&&!v.includes(String(r[c])))return false}else if(v&&String(r[c])!==v)return false}const fd=String(r.Fecha||'').slice(0,10);if(dateFrom&&fd<dateFrom)return false;if(dateTo&&fd>dateTo)return false;if(clientSearch){const h=(String(r.Cliente||'')+' '+String(r.Cod_Cliente||'')).toLowerCase();if(!h.includes(clientSearch))return false}return true});"
d=rep(d,old,new,"filters")

oldbar="function bar(c,rows){let a=group(rows,c.dimension,c.measure,c.op||'sum').sort((x,y)=>y.value-x.value).slice(0,c.top_n||10),mx=Math.max(1,...a.map(x=>Math.abs(x.value)));return shell(c,`<div class=\"bars\">${a.map(x=>`<div class=\"bargrp\" title=\"${esc(x.label)}: ${fmt(x.value)}\"><div class=\"bar\" style=\"height:${Math.max(2,Math.abs(x.value)/mx*100)}%\"></div><span class=\"xlabel\">${esc(x.label)}</span></div>`).join('')}</div>`)}"
newbar="function bar(c,rows){let a=group(rows,c.dimension,c.measure,c.op||'sum').sort((x,y)=>y.value-x.value).slice(0,Math.min(chartTop,c.top_n||chartTop)),mx=Math.max(1,...a.map(x=>Math.abs(x.value)));return shell(c,`<div class=\"bars\">${a.map(x=>`<div class=\"bargrp\" title=\"${esc(x.label)}: ${fmt(x.value)}\"><div class=\"bar ${x.value<0?'negative':''}\" style=\"height:${Math.max(2,Math.abs(x.value)/mx*100)}%\"></div><span class=\"xlabel\">${esc(x.label)}</span></div>`).join('')}</div>`)}"
d=rep(d,oldbar,newbar,"bar")

oldtable="function renderTable(rows){const t=P.table||{},cols=(t.columns||Object.keys(rows[0]||{})).slice(0,12),lim=Math.min(t.limit||100,500);$('tableTitle').textContent=t.title||'Detalle';$('thead').innerHTML='<tr>'+cols.map(c=>`<th>${esc(c)}</th>`).join('')+'</tr>';$('tbody').innerHTML=rows.slice(0,lim).map(r=>'<tr>'+cols.map(c=>`<td>${esc(r[c]??'')}</td>`).join('')+'</tr>').join('');$('rownote').textContent=`Mostrando ${Math.min(rows.length,lim).toLocaleString('es-MX')} de ${rows.length.toLocaleString('es-MX')} registros filtrados.`}"
newtable="let tablePage=1,tablePageSize=25,tableSort='',tableAsc=true;function renderTable(rows){const t=P.table||{},cols=(t.columns||Object.keys(rows[0]||{})),all=[...rows];if(tableSort)all.sort((a,b)=>{const x=a[tableSort],y=b[tableSort];return (typeof x==='number'&&typeof y==='number'?(x-y):String(x??'').localeCompare(String(y??''),'es'))*(tableAsc?1:-1)});const pages=Math.max(1,Math.ceil(all.length/tablePageSize));tablePage=Math.min(tablePage,pages);const start=(tablePage-1)*tablePageSize,view=all.slice(start,start+tablePageSize);$('tableTitle').textContent=t.title||'Detalle';$('thead').innerHTML='<tr>'+cols.map(c=>`<th data-sort=\"${esc(c)}\">${esc(c)}${tableSort===c?(tableAsc?' ▲':' ▼'):''}</th>`).join('')+'</tr>';$('tbody').innerHTML=view.map(r=>'<tr>'+cols.map(c=>`<td data-client=\"${esc(r.Cliente??'')}\" data-product=\"${esc(r.ctrl_alm??r.Articulo??'')}\">${esc(r[c]??'')}</td>`).join('')+'</tr>').join('');$('rownote').innerHTML=`Mostrando ${view.length.toLocaleString('es-MX')} de ${all.length.toLocaleString('es-MX')} registros filtrados. <span class=\"pager\"><button class=\"btn\" id=\"prevPage\">Anterior</button> Página ${tablePage} de ${pages} <button class=\"btn\" id=\"nextPage\">Siguiente</button> <select id=\"pageSize\"><option ${tablePageSize===25?'selected':''}>25</option><option ${tablePageSize===50?'selected':''}>50</option><option ${tablePageSize===100?'selected':''}>100</option></select></span>`;document.querySelectorAll('th[data-sort]').forEach(th=>th.onclick=()=>{const c=th.dataset.sort;if(tableSort===c)tableAsc=!tableAsc;else{tableSort=c;tableAsc=true}renderTable(rows)});document.getElementById('prevPage').onclick=()=>{if(tablePage>1){tablePage--;renderTable(rows)}};document.getElementById('nextPage').onclick=()=>{if(tablePage<pages){tablePage++;renderTable(rows)}};document.getElementById('pageSize').onchange=e=>{tablePageSize=Number(e.target.value)||25;tablePage=1;renderTable(rows)};document.querySelectorAll('#tbody td').forEach(td=>td.ondblclick=()=>openDrill(td.dataset.client,td.dataset.product))}"
d=rep(d,oldtable,newtable,"table")

advjs="function metricTable(rows,cols,limit=20){const show=rows.slice(0,limit);return `<div class=\"adv-table-wrap\"><table class=\"adv-table\"><thead><tr>${cols.map(c=>`<th>${esc(c)}</th>`).join('')}</tr></thead><tbody>${show.map(r=>`<tr>${cols.map(c=>{const v=r[c],cl=(c==='Utilidad'&&Number(v)<0)?'neg':(c==='Utilidad'&&Number(v)>0)?'pos':'';return `<td class=\"${cl}\">${typeof v==='number'?fmt(v,c.includes('Pct')?'percent':undefined):esc(v??'')}</td>`}).join('')}</tr>`).join('')}</tbody></table></div>`}function renderAdvanced(){const A=P.advanced||{};$('execFindings').innerHTML=(A.executive_findings||[]).map(x=>`<div class=\"finding\">${esc(x)}</div>`).join('')||'<div class=\"empty\">Sin hallazgos ejecutivos.</div>';$('clientsAdvanced').innerHTML=metricTable(A.clients||[],['Cliente','Toneladas','Venta','Costo','Utilidad','MargenPct','UtilidadTon'],20);$('productsAdvanced').innerHTML=metricTable(A.products||[],['ctrl_alm','Toneladas','Venta','Costo','Utilidad','MargenPct','UtilidadTon'],20);$('negativeAdvanced').innerHTML=metricTable(A.negative_operations||[],['Fecha','Refer','Cliente','Articulo','Toneladas_Vendidas','Importe_Venta','Costo','Utilidad','Proveedor','Vendedor'],40);$('routesAdvanced').innerHTML=metricTable(A.routes||[],['Ciudad_Origen','Ciudad_Destino','Toneladas','Operaciones','Flete','FleteTon','Venta','Utilidad'],50);const V=A.validation||{};$('validationAdvanced').innerHTML=(V.checks||[]).map(x=>`<div class=\"finding\">${x.ok?'✓':'⚠'} <b>${esc(x.name)}</b><br>${esc(x.detail)}</div>`).join('')}function openDrill(client,product){const rows=filtered().filter(r=>(client&&String(r.Cliente||'')===client)||(product&&String(r.ctrl_alm||r.Articulo||'')===product));if(!rows.length)return;const title=client||product;$('drillTitle').textContent='Detalle · '+title;const ton=rows.reduce((s,r)=>s+num(r.Toneladas_Vendidas),0),venta=rows.reduce((s,r)=>s+num(r.Importe_Venta),0),costo=rows.reduce((s,r)=>s+num(r.Costo),0),util=rows.reduce((s,r)=>s+num(r.Utilidad),0);$('drillBody').innerHTML=`<div class=\"findings\"><div class=\"finding\"><b>Toneladas</b><br>${fmt(ton)}</div><div class=\"finding\"><b>Venta</b><br>${fmt(venta,'currency')}</div><div class=\"finding\"><b>Costo</b><br>${fmt(costo,'currency')}</div><div class=\"finding\"><b>Utilidad</b><br><span class=\"${util<0?'neg':'pos'}\">${fmt(util,'currency')}</span></div><div class=\"finding\"><b>Margen %</b><br>${venta?fmt(100*util/venta,'percent'):'N/A'}</div></div>`+metricTable(rows.slice(0,100),['Fecha','Refer','Cliente','Articulo','ctrl_alm','Toneladas_Vendidas','Importe_Venta','Costo','Utilidad','Proveedor','Almacen','Vendedor'],100);$('drillModal').classList.add('open')}$('drillClose').onclick=()=>$('drillModal').classList.remove('open');$('drillModal').addEventListener('click',e=>{if(e.target.id==='drillModal')$('drillModal').classList.remove('open')});\n"
d=rep(d,"$('csv').onclick=",advjs+"$('csv').onclick=","advanced js")
d=rep(d,"function render(){const r=filtered();renderKpis(r);renderCharts(r);renderTable(r)}","function render(){const r=filtered();renderKpis(r);renderCharts(r);renderTable(r);renderAdvanced()}","render")
DYN.write_text(d,encoding="utf-8")

tests=TESTS.read_text(encoding="utf-8")
marker="def test_r9_5_advanced_analytics_payload():"
if marker not in tests:
    add=(ROOT/"tests_r9_5_append.txt").read_text(encoding="utf-8").rstrip()+"\n\n"
    needle="\nif __name__=='__main__':"
    if needle not in tests: raise SystemExit("ERROR: no se encontró __main__")
    tests=tests.replace(needle,"\n"+add+"if __name__=='__main__':",1)
    TESTS.write_text(tests,encoding="utf-8")

a=ANALYZER.read_text(encoding="utf-8").replace("8.5.5-r9.4","8.5.5-r9.5").replace("V8.5.5 R9.4","V8.5.5 R9.5")
ANALYZER.write_text(a,encoding="utf-8")
print("R9.5 aplicado correctamente.")
print("Backup:",backup)
print("Version objetivo: 8.5.5-r9.5")
