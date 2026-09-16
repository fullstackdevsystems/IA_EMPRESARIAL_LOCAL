from __future__ import annotations

UNIFIED_ADMIN_HTML = r'''<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>IA Empresarial Local - Administración</title>
<style>
.guided-ai{border:1px solid #c7d2fe;background:#fafaff}.guided-ai-choice{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin:12px 0}.guided-ai-choice label{display:block;border:1px solid #cbd5e1;border-radius:10px;padding:10px;cursor:pointer;background:#fff}.guided-ai-choice input{width:auto;margin-right:6px}.guided-ai-status{margin-top:12px}.advanced-ai-toggle{margin-top:12px}@media(max-width:950px){.guided-ai-choice{grid-template-columns:1fr}}
:root{--bg:#f4f7fb;--card:#fff;--ink:#142033;--muted:#64748b;--line:#dbe3ee;--blue:#2563eb;--green:#15803d;--red:#b91c1c;--amber:#b45309;--nav:#0f172a}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font-family:Segoe UI,Arial,sans-serif}.layout{display:grid;grid-template-columns:250px 1fr;min-height:100vh}.side{background:var(--nav);color:#fff;padding:20px 14px}.brand{font-weight:800;font-size:18px;margin:4px 8px 22px}.nav button{width:100%;border:0;background:transparent;color:#cbd5e1;text-align:left;padding:11px 12px;border-radius:9px;margin:2px 0;cursor:pointer}.nav button.active,.nav button:hover{background:#1e293b;color:#fff}.main{padding:24px;min-width:0}.top{display:flex;justify-content:space-between;gap:16px;align-items:center}.links a{margin-left:12px;color:var(--blue);text-decoration:none}.grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:18px 0}.metric,.card{background:var(--card);border:1px solid var(--line);border-radius:14px;box-shadow:0 6px 22px #2342a30c}.metric{padding:15px}.metric b{font-size:24px;display:block;margin-top:4px}.card{padding:18px;margin:14px 0}.panel{display:none}.panel.active{display:block}.row{display:flex;gap:8px;align-items:center;flex-wrap:wrap}input,select,textarea{border:1px solid #cbd5e1;border-radius:8px;padding:8px;width:100%;font:inherit}textarea{min-height:75px}.btn{border:0;border-radius:8px;padding:8px 11px;background:var(--blue);color:#fff;cursor:pointer}.btn.ok{background:var(--green)}.btn.warn{background:var(--amber)}.btn.danger{background:var(--red)}.btn.muted{background:#64748b}.table{overflow:auto}.table table{width:100%;border-collapse:collapse;font-size:13px}.table th,.table td{text-align:left;padding:9px;border-bottom:1px solid #e5e7eb;vertical-align:top}.pill{display:inline-block;padding:3px 7px;border-radius:999px;background:#e2e8f0;font-size:11px}.pill.VALIDADO{background:#dcfce7;color:#166534}.pill.PROPUESTO{background:#fef3c7;color:#92400e}.pill.RECHAZADO,.pill.OBSOLETO{background:#fee2e2;color:#991b1b}.pill.READY,.pill.TESTED{background:#dcfce7;color:#166534}.pill.CONFIGURED{background:#dbeafe;color:#1d4ed8}.pill.DEGRADED{background:#fef3c7;color:#92400e}.pill.BLOCKED{background:#fee2e2;color:#991b1b}.pill.NOT_REQUIRED{background:#e2e8f0;color:#475569}.mutedtxt{color:var(--muted);font-size:12px}.notice{background:#eff6ff;border:1px solid #bfdbfe;border-radius:10px;padding:10px;margin:12px 0}.error{background:#fef2f2;border-color:#fecaca}.formgrid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.actions{white-space:nowrap}.empty{padding:18px;color:var(--muted)}.guided-sql{border:1px solid #bfdbfe;background:#f8fbff}.guided-steps{display:flex;gap:8px;flex-wrap:wrap;margin:12px 0}.guided-step{background:#e2e8f0;border-radius:999px;padding:5px 9px;font-size:12px}.guided-step.active{background:#dbeafe;color:#1d4ed8;font-weight:700}.guided-object-list{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:7px;max-height:320px;overflow:auto;padding:8px;border:1px solid #dbe3ee;border-radius:10px;background:#fff}.guided-object-item{display:flex;align-items:center;gap:8px;padding:7px;border:1px solid #e5e7eb;border-radius:8px}.guided-object-item input{width:auto}.guided-success{background:#f0fdf4;border:1px solid #bbf7d0;border-radius:10px;padding:10px;margin-top:10px}.advanced-sql-toggle{margin-top:12px}@media(max-width:950px){.guided-object-list{grid-template-columns:1fr}}pre{white-space:pre-wrap;background:#0f172a;color:#e2e8f0;padding:12px;border-radius:10px;max-height:420px;overflow:auto}@media(max-width:950px){.layout{grid-template-columns:1fr}.side{position:sticky;top:0;z-index:5;padding:10px}.brand{margin:0 8px 8px}.nav{display:flex;overflow:auto}.nav button{width:auto;white-space:nowrap}.grid{grid-template-columns:repeat(2,1fr)}.formgrid{grid-template-columns:1fr}}
</style></head><body>
<div class="layout"><aside class="side"><div class="brand">IA Empresarial Local<br><span style="font-size:11px;font-weight:400;color:#94a3b8">Administración</span></div><div class="nav" id="nav">
<button data-p="resumen" class="active">Resumen</button><button data-p="controlplane">Plataforma</button><button data-p="memoria">Memoria</button><button data-p="documentos">Documentos / RAG</button><button data-p="semantica">Diccionario</button><button data-p="reglas">Reglas empresariales</button><button data-p="analiticas">Reglas analíticas</button><button data-p="feedback">Feedback</button><button data-p="trazas">Trazabilidad</button><button data-p="historial">Historial</button><button data-p="auditoria">Auditoría</button><button data-p="recuperacion" data-cp-permission="backup:create" data-cp-system-admin="true">Recuperación</button></div></aside>
<main class="main"><div class="top"><div><h2 style="margin:0">Administración empresarial</h2><div class="mutedtxt">Conocimiento, gobernanza, aprendizaje y trazabilidad en una sola consola.</div></div><div class="links"><a id="assistant" href="/assistant">Asistente</a><a href="/">Analizador</a><button class="btn muted" onclick="enterpriseLogout()">Cerrar sesión</button></div></div><div id="auth" class="notice error" style="display:none"></div><div id="msg"></div>
<section id="resumen" class="panel active"><div class="grid" id="metrics"></div><div class="card"><h3>Estado de conocimiento</h3><div id="statusSummary"></div></div></section>
<section id="controlplane" class="panel"><div class="card"><h3>Administración de plataforma</h3><div class="mutedtxt">Administración segura de empresa, usuarios, SQL Server e inteligencia artificial.</div><div id="controlSummary"></div></div><div class="card" id="cpReadinessCard"><h3>Preparación de empresa</h3><div class="mutedtxt">Estado de empresa, administrador, SQL Server, inteligencia artificial e identidad visual. Configurado no equivale a conexión validada.</div><div id="controlReadiness" style="margin-top:10px"></div><div class="row" style="margin-top:10px"><button class="btn muted" data-cp-permission="config:read" onclick="controlLoadReadiness(false)">Actualizar estado</button><button class="btn ok" data-cp-permission="config:read" onclick="controlValidateReadiness()">Validar preparación</button></div></div><div class="card table"><h3>Empresas</h3><div id="controlTenants"></div><div id="cpTenantCreate" data-cp-permission="tenant:update" data-cp-system-admin="true" class="settings" style="margin-top:12px"><label>ID empresa<input id="cpTenantId" autocomplete="off" placeholder="empresa-norte"></label><label>Nombre<input id="cpTenantName" autocomplete="off"></label><label>Unidad de negocio predeterminada<input id="cpTenantBusinessUnit" autocomplete="off"></label><label>Sucursal predeterminada<input id="cpTenantBranch" autocomplete="off"></label><label>Idioma<input id="cpTenantLocale" autocomplete="off" value="es-MX"></label><label>Zona horaria<input id="cpTenantTimezone" autocomplete="off" placeholder="America/Mazatlan"></label></div><button id="cpCreateTenantBtn" class="btn" data-cp-permission="tenant:update" data-cp-system-admin="true" onclick="controlCreateTenant()">Crear empresa</button></div><div class="card table"><h3>Usuarios y roles</h3><div id="controlUsers"></div><div id="cpUserCreate" data-cp-permission="user:create" class="settings" style="margin-top:12px"><label>ID usuario<input id="cpUserId" autocomplete="off"></label><label>Usuario<input id="cpUsername" autocomplete="off"></label><label>Nombre<input id="cpDisplayName" autocomplete="off"></label><label>Roles<input id="cpRoles" value="VIEWER" placeholder="VIEWER o ANALYST"></label><label>Contraseña<input id="cpUserPassword" type="password" autocomplete="new-password"></label></div><button id="cpCreateUserBtn" class="btn" data-cp-permission="user:create" onclick="controlCreateUser()">Crear usuario</button></div>
<div class="card guided-sql" id="guidedSqlCard" data-cp-permission="sql:configure">
<h3>Conectar SQL Server</h3>
<div class="mutedtxt">Conecta la base de datos, comprueba el acceso y elige visualmente la información que esta empresa podrá consultar.</div>
<div class="guided-steps">
<span class="guided-step active">1. Conexión</span>
<span class="guided-step">2. Probar</span>
<span class="guided-step">3. Elegir tablas</span>
<span class="guided-step">4. Guardar</span>
</div>
<div class="formgrid">
<label>Nombre de la fuente
<input id="gsSqlDisplay" autocomplete="off" placeholder="Sistema principal">
</label>
<label>Servidor
<input id="gsSqlServer" autocomplete="off" placeholder="SERVIDOR\INSTANCIA" oninput="guidedSqlInvalidate()">
</label>
<label>Base de datos
<input id="gsSqlDatabase" autocomplete="off" placeholder="Nombre de la base" oninput="guidedSqlInvalidate()">
</label>
<label>Tipo de acceso
<select id="gsSqlAuth" onchange="guidedSqlAuthChanged();guidedSqlInvalidate()">
<option value="WINDOWS_INTEGRATED">Usar cuenta de Windows</option>
<option value="SQL_AUTH">Usuario y contraseña de SQL Server</option>
</select>
</label>
<label id="gsSqlUsernameWrap" style="display:none">Usuario SQL
<input id="gsSqlUsername" autocomplete="off" oninput="guidedSqlInvalidate()">
</label>
<label id="gsSqlSecretWrap" style="display:none">Contraseña SQL
<input id="gsSqlSecret" type="password" autocomplete="new-password" oninput="guidedSqlInvalidate()">
</label>
</div>
<div class="row" style="margin-top:12px">
<button id="gsSqlProbeBtn" class="btn" data-cp-permission="sql:configure" onclick="guidedSqlProbe()">Probar conexión y buscar tablas</button>
</div>
<div id="gsSqlStatus"></div>
<div id="gsSqlObjects" style="display:none;margin-top:12px"></div>
<div id="gsSqlSelectionActions" class="row" style="display:none;margin-top:10px">
<button class="btn muted" type="button" onclick="guidedSqlSelectAll(true)">Seleccionar todo</button>
<button class="btn muted" type="button" onclick="guidedSqlSelectAll(false)">Quitar selección</button>
<button id="gsSqlSaveBtn" class="btn ok" type="button" disabled onclick="guidedSqlSave()">Guardar fuente SQL</button>
</div>
</div>
<div class="card table"><h3>Fuentes SQL Server</h3>
<div class="mutedtxt">Conexiones configuradas. Las opciones técnicas permanecen disponibles sólo en configuración avanzada.</div>
<div id="controlSql"></div>
<button id="cpSqlAdvancedToggle" class="btn muted advanced-sql-toggle" data-cp-permission="sql:configure" onclick="controlToggleSqlAdvanced()">Configuración avanzada</button>
<div id="cpSqlCreate" data-cp-permission="sql:configure" data-cp-advanced-sql="true" class="settings" style="margin-top:12px;display:none"><label>ID conexión<input id="cpSqlId" autocomplete="off"></label><label>Nombre<input id="cpSqlDisplay" autocomplete="off"></label><label>Servidor<input id="cpSqlServer" autocomplete="off"></label><label>Base de datos<input id="cpSqlDatabase" autocomplete="off"></label><label>Autenticación<select id="cpSqlAuth"><option value="WINDOWS_INTEGRATED">Autenticación integrada de Windows</option><option value="SQL_AUTH">Autenticación de SQL Server</option></select></label><label>Usuario SQL<input id="cpSqlUsername" autocomplete="off"></label><label>Credencial SQL<input id="cpSqlSecret" type="password" autocomplete="new-password"></label><label>Esquemas permitidos<input id="cpSqlSchemas" value="dbo" placeholder="dbo"></label><label>Objetos permitidos<input id="cpSqlTables" placeholder="dbo.Tabla"></label><label>Máximo de filas<input id="cpSqlMaxRows" type="number" min="1" max="5000" value="500"></label></div><button id="cpCreateSqlBtn" class="btn" data-cp-permission="sql:configure" data-cp-advanced-sql="true" style="display:none" onclick="controlCreateSql()">Crear conexión SQL</button></div><div class="card"><h3>Proveedor de inteligencia artificial</h3><div id="controlAi"></div><div id="cpAiEditor" data-cp-permission="config:read" class="settings" style="margin-top:12px"><label>Tipo de proveedor<select id="cpAiType" onchange="controlAiProviderChanged()"><option value="DISABLED">Desactivado</option><option value="OLLAMA">Ollama</option><option value="OPENAI_COMPATIBLE_LOCAL">Compatible local con OpenAI</option></select></label><label>URL local<input id="cpAiUrl" autocomplete="off" placeholder="http://localhost:11434" onchange="controlAiProviderChanged()"></label><label>Modelo<select id="cpAiModel" onchange="guidedAiInvalidate()"><option value="">Cargando modelos…</option></select></label><label>Tiempo máximo de espera (segundos)<input id="cpAiTimeout" type="number" min="1" max="120" value="30"></label><label>Ventana de contexto<input id="cpAiContext" type="number" min="1"></label><label>Habilitado<select id="cpAiEnabled"><option value="true">Sí</option><option value="false">No</option></select></label></div><button class="btn" data-cp-permission="config:read" onclick="controlTestAi()">Probar proveedor</button> <button class="btn ok" data-cp-permission="config:write" onclick="controlSaveAi()">Guardar proveedor</button></div></section>
<section id="recuperacion" class="panel">
<div class="card">
<h3>Respaldo y recuperación del sistema</h3>
<div class="notice">
Estas operaciones abarcan el estado persistente completo de IA Empresarial Local.
El servicio local se detendrá brevemente para obtener una copia consistente o para restaurar el respaldo.
Los secretos locales de ejecución no se incluyen en los respaldos.
</div>
<div class="row">
<button class="btn ok"
 data-cp-permission="backup:create"
 data-cp-system-admin="true"
 onclick="maintenanceCreateBackup()">
Crear respaldo
</button>
<button class="btn muted"
 data-cp-permission="backup:create"
 data-cp-system-admin="true"
 onclick="loadMaintenanceJobs()">
Actualizar operaciones
</button>
</div>
<div id="maintenanceStatus" class="mutedtxt" style="margin-top:10px"></div>
</div>
<div class="card">
<h3>Restaurar respaldo</h3>
<div class="notice error">
La restauración reemplaza el estado persistente administrado.
El archivo se valida antes de detener el servicio y se valida nuevamente durante la recuperación.
</div>
<input id="maintenanceRestoreFile" type="file" accept=".zip,application/zip">
<label style="margin-top:10px">
Escribe RESTAURAR para confirmar
<input id="maintenanceRestoreConfirm"
 autocomplete="off"
 placeholder="RESTAURAR">
</label>
<button class="btn danger"
 data-cp-permission="backup:restore"
 data-cp-system-admin="true"
 onclick="maintenanceRestore()">
Restaurar respaldo
</button>
</div>
<div class="card table">
<h3>Operaciones recientes</h3>
<div id="maintenanceJobs"></div>
</div>
</section><section id="memoria" class="panel"><div class="card"><h3>Memoria permanente</h3><div class="formgrid"><input id="memText" placeholder="Conocimiento o preferencia"><select id="memCategory"><option>conocimiento_empresa</option><option>regla_negocio</option><option>definicion</option><option>preferencia</option><option>procedimiento</option></select></div><div style="margin-top:8px"><button class="btn" onclick="createMemory()">Guardar memoria</button></div></div><div class="card table" id="memoryTable"></div></section>
<section id="documentos" class="panel"><div class="card"><h3>Documentos / RAG</h3><input type="file" id="docFile"><div style="margin-top:8px"><button class="btn" onclick="uploadDoc()">Indexar documento</button></div></div><div class="card table" id="docsTable"></div></section>
<section id="semantica" class="panel"><div class="card"><h3>Diccionario empresarial</h3><div class="formgrid"><input id="semPhysical" placeholder="Nombre físico: Cve_Clie"><input id="semName" placeholder="Concepto: customer_id"><input id="semArea" placeholder="Área (opcional)"><input id="semDesc" placeholder="Descripción"></div><div style="margin-top:8px"><button class="btn" onclick="proposeSemantic()">Crear propuesta</button></div></div><div class="card table" id="semanticTable"></div></section>
<section id="reglas" class="panel"><div class="card"><h3>Reglas empresariales</h3><div class="formgrid"><input id="ruleName" placeholder="Nombre: UTILIDAD_REAL"><input id="ruleArea" placeholder="Área"><textarea id="ruleExpression" placeholder="Expresión: Venta - Costo - Flete"></textarea><textarea id="ruleDesc" placeholder="Descripción"></textarea></div><button class="btn" onclick="proposeRule()">Crear propuesta</button></div><div class="card table" id="rulesTable"></div></section>
<section id="analiticas" class="panel"><div class="card"><h3>Bindings analíticos</h3><div class="mutedtxt">Vincula una regla VALIDADO con una función del motor determinístico.</div><div class="formgrid"><input id="bindRule" placeholder="ID de regla VALIDADO"><select id="bindType"><option value="metric">metric</option><option value="row_filter">row_filter</option></select><input id="bindTarget" placeholder="Target: profit / sales_valid / commission"><input id="bindPriority" value="100" type="number"></div><button class="btn" onclick="bindAnalytic()">Vincular regla</button></div><div class="card table" id="analyticTable"></div></section>
<section id="feedback" class="panel"><div class="card"><h3>Feedback y propuestas</h3><div class="mutedtxt">Una corrección permanece PROPUESTO hasta validación explícita.</div></div><div class="card table" id="feedbackTable"></div></section>
<section id="trazas" class="panel"><div class="card"><h3>Trazabilidad</h3><div id="traceExplain"></div></div><div class="card table" id="traceTable"></div></section>
<section id="historial" class="panel"><div class="card"><h3>Historial / versiones</h3><div class="formgrid"><select id="histType"><option value="business_rule">business_rule</option><option value="semantic_definition">semantic_definition</option></select><input id="histId" placeholder="ID del objeto"></div><button class="btn" onclick="loadHistory()">Consultar historial</button><div id="historyOut"></div></div></section>
<section id="auditoria" class="panel"><div class="card"><h3>Auditoría</h3><div class="table" id="auditTable"></div></div></section>
</main></div>
<script>
let token=sessionStorage.getItem('iaEnterpriseSession')||'',currentUser=null;document.getElementById('assistant').href='/assistant';
const H=()=>({'Authorization':'Bearer '+token});const J=()=>({'Authorization':'Bearer '+token,'Content-Type':'application/json'});const esc=x=>String(x??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
function toast(t,err=false){document.getElementById('msg').innerHTML='<div class="notice '+(err?'error':'')+'>'+esc(t)+'</div>';setTimeout(()=>document.getElementById('msg').innerHTML='',4500)}
function showLogin(message=''){token='';currentUser=null;sessionStorage.removeItem('iaEnterpriseSession');document.querySelectorAll('.panel,.side').forEach(x=>x.style.display='none');const a=document.getElementById('auth');a.style.display='block';a.innerHTML='<h3>Acceso empresarial</h3><input id="authUser" autocomplete="username" placeholder="Usuario"><input id="authPassword" type="password" autocomplete="current-password" placeholder="Contraseña"><button class="btn" onclick="enterpriseLogin()">Iniciar sesión</button><div class="small">'+esc(message)+'</div>'}
function can(permission){const p=(currentUser&&currentUser.effective_permissions)||[];return p.includes('*')||p.includes(permission)}
function applyCapabilities(){const map={createMemory:'knowledge:write',confirmMem:'knowledge:write',deleteMem:'knowledge:write',uploadDoc:'knowledge:write',reindexDoc:'knowledge:write',deleteDoc:'knowledge:write',proposeSemantic:'knowledge:write',validateSem:'knowledge:write',rejectSem:'knowledge:write',proposeRule:'knowledge:write',validateRule:'knowledge:write',rejectRule:'knowledge:write',obsoleteRule:'knowledge:write',bindAnalytic:'knowledge:write',validateFeedback:'knowledge:write',rejectFeedback:'knowledge:write'};document.querySelectorAll('button[onclick]').forEach(b=>{const fn=(b.getAttribute('onclick')||'').match(/^(\w+)/);if(fn&&map[fn[1]])b.style.display=can(map[fn[1]])?'':'none'});document.querySelectorAll('#nav button').forEach(b=>{if(['resumen','trazas','auditoria'].includes(b.dataset.p))b.style.display=can('admin:audit')?'':'none';if(b.dataset.p==='controlplane')b.style.display=(can('config:read')||can('tenant:list')||can('user:list')||can('sql:read'))?'':'none'});controlApplyCapabilities()}
function showConsole(){document.getElementById('auth').style.display='none';document.querySelectorAll('.panel').forEach(x=>x.style.display='');document.querySelector('.side').style.display='';applyCapabilities()}
async function establishSession(){try{const me=await fetch('/api/auth/me',{headers:H()});if(!me.ok){showLogin(me.status===401?'Sesión inválida.':'No se pudo validar la sesión.');return false}currentUser=await me.json();showConsole();return true}catch(e){showLogin('No se pudo conectar con el servidor local.');return false}}
async function enterpriseLogin(){const u=document.getElementById('authUser').value,p=document.getElementById('authPassword');try{const r=await fetch('/api/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:u,password:p.value})});let d={};try{d=await r.json()}catch{}if(!r.ok){showLogin('Credenciales inválidas o acceso no disponible.');return}token=d.token;sessionStorage.setItem('iaEnterpriseSession',token);if(await establishSession())refreshAll()}catch(e){showLogin('No se pudo conectar con el servidor local.')}finally{p.value=''}}
async function enterpriseLogout(){try{if(token)await fetch('/api/auth/logout',{method:'POST',headers:H()})}finally{showLogin('Sesión cerrada.')}}
async function api(url,opt={}){const r=await fetch(url,opt);let d={};try{d=await r.json()}catch{}if(r.status===401){showLogin('La sesión expiró o fue revocada.');throw new Error('Sesión requerida')}if(!r.ok)throw new Error(d.detail||d.error||('HTTP '+r.status));return d}
function pill(s){return '<span class="pill '+esc(s)+'">'+esc(s||'N/D')+'</span>'}function table(rows,cols,actions){if(!rows||!rows.length)return '<div class="empty">Sin registros.</div>';return '<table><thead><tr>'+cols.map(c=>'<th>'+esc(c[0])+'</th>').join('')+(actions?'<th>Acciones</th>':'')+'</tr></thead><tbody>'+rows.map(r=>'<tr>'+cols.map(c=>'<td>'+(c[2]?c[2](r[c[1]],r):esc(r[c[1]]??''))+'</td>').join('')+(actions?'<td class="actions">'+actions(r)+'</td>':'')+'</tr>').join('')+'</tbody></table>'}
async function refreshAll(){if(!token)return;try{const [m,d,s,r,a,f]=await Promise.all([api('/api/enterprise/memories?include_inactive=true',{headers:H()}),api('/api/enterprise/documents',{headers:H()}),api('/api/enterprise/semantic-definitions?include_inactive=true',{headers:H()}),api('/api/enterprise/business-rules?include_inactive=true',{headers:H()}),api('/api/enterprise/analytic-rules',{headers:H()}),api('/api/enterprise/feedback',{headers:H()})]);renderMem(m.memories);renderDocs(d.documents);renderSem(s.items);renderRules(r.items);renderAnalytic(a.items);renderFeedback(f.feedback||f.items);applyCapabilities();if(can('admin:audit')){const [ov,t]=await Promise.all([api('/api/enterprise/admin/overview',{headers:H()}),api('/api/enterprise/traces?limit=100',{headers:H()})]);renderOverview(ov);renderTraces(t.traces);loadAudit()}else{document.getElementById('metrics').innerHTML='';document.getElementById('statusSummary').innerHTML='<div class="empty">Resumen administrativo no autorizado.</div>'}}catch(e){toast(e.message,true)}}
let CONTROL_TENANTS=[];
let CONTROL_USERS=[];
let CONTROL_SQL=[];

function controlSystemAdmin(){
    return Boolean(
        currentUser &&
        (currentUser.roles||[]).includes('SYSTEM_ADMIN')
    )
}

function controlElement(id){
    return document.getElementById(id)
}

function controlTenantId(){
    const selector=controlElement('cpTenantSelect');
    return String(
        (selector&&selector.value) ||
        (currentUser&&currentUser.tenant_id) ||
        ''
    ).trim().toLowerCase()
}

function controlTenantQuery(){
    const tenant=controlTenantId();
    if(!controlSystemAdmin())return '';
    return tenant?'?tenant_id='+encodeURIComponent(tenant):''
}

function controlCsv(value){
    return String(value||'')
        .split(',')
        .map(x=>x.trim())
        .filter(Boolean)
}

function controlApplyCapabilities(){
    document.querySelectorAll('[data-cp-permission]').forEach(el=>{
        el.style.display=can(el.dataset.cpPermission)?'':'none'
    });
    document.querySelectorAll('[data-cp-system-admin]').forEach(el=>{
        el.style.display=(controlSystemAdmin()&&can(el.dataset.cpPermission))?'':'none'
    });
    controlApplySqlAdvancedVisibility()
}

let CONTROL_SQL_ADVANCED=false;

function controlApplySqlAdvancedVisibility(){
    document.querySelectorAll('[data-cp-advanced-sql]').forEach(el=>{
        el.style.display=(
            CONTROL_SQL_ADVANCED &&
            can('sql:configure')
        )?'':'none'
    });

    const toggle=controlElement('cpSqlAdvancedToggle');

    if(toggle){
        toggle.textContent=
            CONTROL_SQL_ADVANCED
                ?'Ocultar configuración avanzada'
                :'Configuración avanzada'
    }
}

function controlToggleSqlAdvanced(){
    if(!can('sql:configure'))return;
    CONTROL_SQL_ADVANCED=!CONTROL_SQL_ADVANCED;
    controlApplySqlAdvancedVisibility();
    controlRenderSqlTable()
}

function controlUnavailable(id,message){
    const el=controlElement(id);
    if(el)el.innerHTML='<div class="empty">'+esc(message)+'</div>'
}

async function controlLoadOverview(){
    if(!can('config:read')){
        controlUnavailable('controlSummary','Resumen no autorizado.');
        return
    }
    try{
        const o=await api(
            '/api/enterprise/control-plane/overview',
            {headers:H()}
        );
        const summary={
            release:o.release,
            tenant:o.active_tenant,
            user:o.active_user,
            health:o.health
        };
        controlElement('controlSummary').innerHTML=
            '<pre>'+esc(JSON.stringify(summary,null,2))+'</pre>'
    }catch(e){
        controlUnavailable('controlSummary',e.message)
    }
}

function controlTenantActions(tenant){
    const actions=[];

    if(!can('tenant:update'))return '';

    actions.push(
        '<button class="btn" onclick="controlEditTenant(\''+
        esc(tenant.tenant_id)+
        '\')">Editar</button>'
    );

    const ownTenant=String(
        (currentUser&&currentUser.tenant_id)||''
    ).toLowerCase()===String(
        tenant.tenant_id||''
    ).toLowerCase();

    if(tenant.status==='ACTIVE'){
        if(!(controlSystemAdmin()&&ownTenant)){
            actions.push(
                '<button class="btn danger" onclick="controlTenantState(\''+
                esc(tenant.tenant_id)+
                '\',\'disable\')">Deshabilitar</button>'
            )
        }
    }else{
        actions.push(
            '<button class="btn ok" onclick="controlTenantState(\''+
            esc(tenant.tenant_id)+
            '\',\'enable\')">Habilitar</button>'
        )
    }

    return actions.join(' ')
}

async function controlLoadTenants(){
    if(!can('tenant:list')){
        controlUnavailable(
            'controlTenants',
            'Empresas no autorizadas.'
        );
        return
    }

    try{
        const data=await api(
            '/api/admin/tenants',
            {headers:H()}
        );

        CONTROL_TENANTS=data.tenants||[];

        const selected=controlTenantId();

        let selector='';

        if(controlSystemAdmin()){
            selector=
                '<label class="small">Empresa activa para administrar '+
                '<select id="cpTenantSelect" onchange="controlTenantChanged()">'+
                CONTROL_TENANTS.map(t=>
                    '<option value="'+esc(t.tenant_id)+'">'+
                    esc(t.name||t.tenant_id)+
                    (t.status==='ACTIVE'?'':' [DESHABILITADA]')+
                    '</option>'
                ).join('')+
                '</select></label>'
        }else{
            selector=
                '<div class="small">Empresa activa: '+
                esc(controlTenantId())+
                '</div>'
        }

        controlElement('controlTenants').innerHTML=
            selector+
            table(
                CONTROL_TENANTS,
                [
                    ['Tenant','tenant_id'],
                    ['Nombre','name'],
                    ['Unidad','default_business_unit'],
                    ['Sucursal','default_branch'],
                    ['Estado','status',(v)=>pill(v)]
                ],
                can('tenant:update')
                    ?controlTenantActions
                    :null
            );

        const select=controlElement('cpTenantSelect');

        if(select){
            const exists=[...select.options]
                .some(x=>x.value===selected);

            if(exists){
                select.value=selected
            }else if(select.options.length){
                select.value=select.options[0].value
            }
        }

        controlApplyCapabilities()
    }catch(e){
        controlUnavailable(
            'controlTenants',
            e.message
        )
    }
}

async function controlCreateTenant(){
    if(
        !controlSystemAdmin() ||
        !can('tenant:update')
    )return;

    const tenantId=controlElement(
        'cpTenantId'
    ).value.trim().toLowerCase();

    const name=controlElement(
        'cpTenantName'
    ).value.trim();

    const businessUnit=controlElement(
        'cpTenantBusinessUnit'
    ).value.trim();

    const branch=controlElement(
        'cpTenantBranch'
    ).value.trim();

    const locale=controlElement(
        'cpTenantLocale'
    ).value.trim();

    const timezone=controlElement(
        'cpTenantTimezone'
    ).value.trim();

    try{
        if(!tenantId||!name){
            throw new Error(
                'ID y nombre de empresa son obligatorios.'
            )
        }

        if(
            !/^[a-z0-9][a-z0-9_.-]{0,79}$/.test(
                tenantId
            )
        ){
            throw new Error(
                'ID de empresa no valido.'
            )
        }

        const settings={};

        if(locale){
            settings.locale=locale
        }

        if(timezone){
            settings.timezone=timezone
        }

        const body={
            tenant_id:tenantId,
            name,
            default_business_unit:
                businessUnit||null,
            default_branch:
                branch||null
        };

        if(Object.keys(settings).length){
            body.settings=settings
        }

        await api(
            '/api/admin/tenants',
            {
                method:'POST',
                headers:{
                    ...H(),
                    'Content-Type':'application/json'
                },
                body:JSON.stringify(body)
            }
        );

        controlElement('cpTenantId').value='';
        controlElement('cpTenantName').value='';
        controlElement('cpTenantBusinessUnit').value='';
        controlElement('cpTenantBranch').value='';
        controlElement('cpTenantLocale').value='es-MX';
        controlElement('cpTenantTimezone').value='';

        await controlLoadTenants();

        const selector=controlElement(
            'cpTenantSelect'
        );

        if(selector){
            selector.value=tenantId;
            await controlTenantChanged()
        }

        toast('Empresa creada.')
    }catch(e){
        toast(e.message,true)
    }
}

async function controlEditTenant(tenantId){
    if(!can('tenant:update'))return;

    const tenant=CONTROL_TENANTS.find(
        x=>x.tenant_id===tenantId
    );

    if(!tenant)return;

    const name=prompt(
        'Nombre de empresa:',
        tenant.name||''
    );

    if(name===null)return;

    const businessUnit=prompt(
        'Unidad de negocio predeterminada:',
        tenant.default_business_unit||''
    );

    if(businessUnit===null)return;

    const branch=prompt(
        'Sucursal predeterminada:',
        tenant.default_branch||''
    );

    if(branch===null)return;

    const currentSettings={
        ...(tenant.settings||{})
    };

    const locale=prompt(
        'Locale:',
        currentSettings.locale||''
    );

    if(locale===null)return;

    const timezone=prompt(
        'Zona horaria:',
        currentSettings.timezone||''
    );

    if(timezone===null)return;

    try{
        if(!String(name).trim()){
            throw new Error(
                'Nombre de empresa obligatorio.'
            )
        }

        const settings={
            ...currentSettings
        };

        if(String(locale).trim()){
            settings.locale=String(locale).trim()
        }else{
            delete settings.locale
        }

        if(String(timezone).trim()){
            settings.timezone=String(timezone).trim()
        }else{
            delete settings.timezone
        }

        await api(
            '/api/admin/tenants/'+
            encodeURIComponent(tenantId),
            {
                method:'PATCH',
                headers:{
                    ...H(),
                    'Content-Type':'application/json'
                },
                body:JSON.stringify({
                    name:String(name).trim(),
                    default_business_unit:
                        String(businessUnit).trim(),
                    default_branch:
                        String(branch).trim(),
                    settings
                })
            }
        );

        toast('Empresa actualizada.');

        await Promise.allSettled([
            controlLoadTenants(),
            controlLoadOverview()
        ])
    }catch(e){
        toast(e.message,true)
    }
}

async function controlTenantState(tenantId,action){
    if(!can('tenant:update'))return;

    if(!['enable','disable'].includes(action)){
        return
    }

    const tenant=CONTROL_TENANTS.find(
        x=>x.tenant_id===tenantId
    );

    if(!tenant)return;

    const ownTenant=String(
        (currentUser&&currentUser.tenant_id)||''
    ).toLowerCase()===String(
        tenantId||''
    ).toLowerCase();

    if(
        action==='disable' &&
        controlSystemAdmin() &&
        ownTenant
    ){
        toast(
            'No se permite deshabilitar desde la consola la empresa de la sesion SYSTEM_ADMIN.',
            true
        );
        return
    }

    if(action==='disable'){
        const approved=confirm(
            'Deshabilitar empresa "'+
            (tenant.name||tenantId)+
            '"? Los usuarios de esa empresa perderan acceso.'
        );

        if(!approved)return
    }

    try{
        const result=await api(
            '/api/admin/tenants/'+
            encodeURIComponent(tenantId)+
            '/'+action,
            {
                method:'POST',
                headers:H()
            }
        );

        if(
            action==='disable' &&
            ownTenant &&
            !controlSystemAdmin()
        ){
            showLogin(
                'La empresa fue deshabilitada. Se cerro la sesion local.'
            );
            return
        }

        toast(
            action==='enable'
                ?'Empresa habilitada.'
                :'Empresa deshabilitada.'
        );

        await controlLoadTenants();

        if(
            controlSystemAdmin() &&
            controlTenantId()===tenantId
        ){
            await Promise.allSettled([
                controlLoadUsers(),
                controlLoadSql(),
                controlLoadAi(),
                controlLoadOverview()
            ])
        }

        return result
    }catch(e){
        toast(e.message,true)
    }
}

async function controlTenantChanged(){
    await Promise.allSettled([
        controlLoadOverview(),
        controlLoadUsers(),
        controlLoadSql(),
        controlLoadAi(),
        controlLoadReadiness(false)
    ]);
    controlApplyCapabilities()
}

function controlUserActions(user){
    const actions=[];

    if(can('user:update')){
        actions.push(
            '<button class="btn" onclick="controlEditUser(\''+
            esc(user.user_id)+
            '\')">Editar</button>'
        );
        actions.push(
            '<button class="btn muted" onclick="controlResetPassword(\''+
            esc(user.user_id)+
            '\')">Reset clave</button>'
        )
    }

    if(can('user:disable')){
        const action=user.status==='ACTIVE'?'disable':'enable';
        const label=user.status==='ACTIVE'?'Deshabilitar':'Habilitar';
        actions.push(
            '<button class="btn" onclick="controlUserState(\''+
            esc(user.user_id)+'\',\''+action+
            '\')">'+label+'</button>'
        )
    }

    return actions.join(' ')
}

async function controlLoadUsers(){
    if(!can('user:list')){
        controlUnavailable('controlUsers','Usuarios no autorizados.');
        return
    }

    try{
        const data=await api(
            '/api/admin/users',
            {headers:H()}
        );

        CONTROL_USERS=data.users||[];

        const tenant=controlTenantId();

        const visible=controlSystemAdmin()
            ? CONTROL_USERS.filter(
                x=>String(x.tenant_id||'').toLowerCase()===tenant
              )
            : CONTROL_USERS;

        controlElement('controlUsers').innerHTML=
            table(
                visible,
                [
                    ['Usuario','username'],
                    ['Nombre','display_name'],
                    ['Rol','roles',(v)=>esc((v||[]).join(', '))],
                    ['Estado','status',(v)=>pill(v)]
                ],
                controlUserActions
            )
    }catch(e){
        controlUnavailable('controlUsers',e.message)
    }
}

async function controlCreateUser(){
    if(!can('user:create'))return;

    const password=controlElement('cpUserPassword');
    const tenant=controlTenantId();

    try{
        const body={
            user_id:controlElement('cpUserId').value.trim(),
            username:controlElement('cpUsername').value.trim(),
            display_name:controlElement('cpDisplayName').value.trim(),
            password:password.value,
            tenant_id:tenant,
            roles:controlCsv(controlElement('cpRoles').value)
        };

        if(!body.user_id||!body.username||!body.password||!body.roles.length){
            throw new Error(
                'ID, usuario, contrasena y rol son obligatorios.'
            )
        }

        await api(
            '/api/admin/users',
            {
                method:'POST',
                headers:{...H(),'Content-Type':'application/json'},
                body:JSON.stringify(body)
            }
        );

        controlElement('cpUserId').value='';
        controlElement('cpUsername').value='';
        controlElement('cpDisplayName').value='';
        controlElement('cpRoles').value='VIEWER';

        toast('Usuario creado.');
        await controlLoadUsers()
    }catch(e){
        toast(e.message,true)
    }finally{
        password.value=''
    }
}

async function controlEditUser(userId){
    const user=CONTROL_USERS.find(x=>x.user_id===userId);
    if(!user||!can('user:update'))return;

    const display=prompt(
        'Nombre visible:',
        user.display_name||''
    );

    if(display===null)return;

    const body={display_name:display};

    if(can('user:role_assign')){
        const roles=prompt(
            'Roles separados por coma:',
            (user.roles||[]).join(',')
        );

        if(roles===null)return;

        body.roles=controlCsv(roles)
    }

    try{
        await api(
            '/api/admin/users/'+encodeURIComponent(userId),
            {
                method:'PATCH',
                headers:{...H(),'Content-Type':'application/json'},
                body:JSON.stringify(body)
            }
        );

        toast('Usuario actualizado.');
        await controlLoadUsers()
    }catch(e){
        toast(e.message,true)
    }
}

async function controlUserState(userId,action){
    if(!can('user:disable'))return;

    try{
        await api(
            '/api/admin/users/'+encodeURIComponent(userId)+'/'+action,
            {method:'POST',headers:H()}
        );

        toast(
            action==='disable'
                ?'Usuario deshabilitado.'
                :'Usuario habilitado.'
        );

        await controlLoadUsers()
    }catch(e){
        toast(e.message,true)
    }
}

async function controlResetPassword(userId){
    if(!can('user:update'))return;

    let password=prompt('Nueva contrasena:');

    if(password===null)return;

    try{
        if(!password)throw new Error('Contrasena requerida.');

        await api(
            '/api/admin/users/'+
            encodeURIComponent(userId)+
            '/reset-password',
            {
                method:'POST',
                headers:{...H(),'Content-Type':'application/json'},
                body:JSON.stringify({password})
            }
        );

        toast('Contrasena restablecida.')
    }catch(e){
        toast(e.message,true)
    }finally{
        password=''
    }
}


let GUIDED_SQL_PROBE=null;

function guidedSqlAuthChanged(){
    const sqlAuth=
        controlElement('gsSqlAuth').value==='SQL_AUTH';

    controlElement('gsSqlUsernameWrap').style.display=
        sqlAuth?'':'none';

    controlElement('gsSqlSecretWrap').style.display=
        sqlAuth?'':'none';

    if(!sqlAuth){
        controlElement('gsSqlUsername').value='';
        controlElement('gsSqlSecret').value=''
    }
}

function guidedSqlInvalidate(){
    GUIDED_SQL_PROBE=null;

    const status=controlElement('gsSqlStatus');
    const objects=controlElement('gsSqlObjects');
    const actions=controlElement('gsSqlSelectionActions');
    const save=controlElement('gsSqlSaveBtn');

    if(status)status.innerHTML='';
    if(objects){
        objects.innerHTML='';
        objects.style.display='none'
    }
    if(actions)actions.style.display='none';
    if(save)save.disabled=true
}

function guidedSqlSlug(value){
    return String(value||'')
        .normalize('NFD')
        .replace(/[\u0300-\u036f]/g,'')
        .toLowerCase()
        .replace(/[^a-z0-9]+/g,'-')
        .replace(/^-+|-+$/g,'')
        .slice(0,48)
}

function guidedSqlConnectionId(){
    const database=
        controlElement('gsSqlDatabase').value.trim();

    const display=
        controlElement('gsSqlDisplay').value.trim();

    const slug=
        guidedSqlSlug(database||display||'principal') ||
        'principal';

    const base='sql-'+slug;

    let candidate=base;
    let number=2;

    while(
        CONTROL_SQL.some(
            item=>String(item.connection_id||'')===candidate
        )
    ){
        candidate=base+'-'+number;
        number+=1
    }

    return candidate
}

function guidedSqlPayload(){
    const auth=controlElement('gsSqlAuth').value;

    const body={
        server:controlElement('gsSqlServer').value.trim(),
        database:controlElement('gsSqlDatabase').value.trim(),
        auth_mode:auth,
        username:controlElement('gsSqlUsername').value.trim()
    };

    if(!body.server||!body.database){
        throw new Error(
            'Indica el servidor y la base de datos.'
        )
    }

    if(auth==='SQL_AUTH'){
        const password=controlElement('gsSqlSecret').value;

        if(!body.username||!password){
            throw new Error(
                'Indica el usuario y la contraseña de SQL Server.'
            )
        }

        body.password=password
    }

    return body
}

async function guidedSqlRequest(url,opt={}){
    const response=await fetch(url,opt);

    let data={};

    try{
        data=await response.json()
    }catch{}

    if(response.status===401){
        showLogin(
            'La sesión expiró o fue revocada.'
        );
        throw new Error('Sesión requerida')
    }

    if(!response.ok){
        const detail=data&&data.detail;

        if(
            detail &&
            typeof detail==='object'
        ){
            throw new Error(
                detail.message ||
                detail.code ||
                ('HTTP '+response.status)
            )
        }

        throw new Error(
            detail ||
            data.error ||
            ('HTTP '+response.status)
        )
    }

    return data
}

function guidedSqlRenderObjects(objects){
    const container=controlElement('gsSqlObjects');

    if(!objects||!objects.length){
        container.innerHTML=
            '<div class="empty">La conexión funcionó, pero no se encontraron tablas o vistas disponibles.</div>';
        container.style.display='';
        controlElement('gsSqlSelectionActions').style.display='none';
        return
    }

    container.innerHTML=
        '<div class="mutedtxt" style="margin-bottom:8px">'+
        'Selecciona únicamente la información que esta empresa podrá consultar.'+
        '</div>'+
        '<div class="guided-object-list">'+
        objects.map((item,index)=>
            '<label class="guided-object-item">'+
            '<input type="checkbox" class="gsSqlObject" '+
            'data-schema="'+esc(item.schema||'')+'" '+
            'data-qualified="'+esc(item.qualified_name||'')+'" '+
            'onchange="guidedSqlSelectionChanged()">'+
            '<span><b>'+esc(item.name||'')+'</b>'+
            '<br><span class="mutedtxt">'+
            esc(item.schema||'')+
            (
                item.type
                    ?' · '+esc(item.type)
                    :''
            )+
            '</span></span>'+
            '</label>'
        ).join('')+
        '</div>';

    container.style.display='';
    controlElement('gsSqlSelectionActions').style.display='flex';
    guidedSqlSelectionChanged()
}

function guidedSqlSelectionChanged(){
    const selected=
        document.querySelectorAll('.gsSqlObject:checked').length;

    const save=controlElement('gsSqlSaveBtn');

    if(save){
        save.disabled=(
            !GUIDED_SQL_PROBE ||
            selected===0
        )
    }
}

function guidedSqlSelectAll(selected){
    document.querySelectorAll('.gsSqlObject').forEach(item=>{
        item.checked=Boolean(selected)
    });

    guidedSqlSelectionChanged()
}

async function guidedSqlProbe(){
    if(!can('sql:configure'))return;

    const button=controlElement('gsSqlProbeBtn');
    const status=controlElement('gsSqlStatus');

    try{
        guidedSqlInvalidate();

        const body=guidedSqlPayload();

        button.disabled=true;
        button.textContent='Probando conexión...';

        status.innerHTML=
            '<div class="notice">Comprobando acceso al servidor local...</div>';

        const result=await guidedSqlRequest(
            '/api/admin/sql/probe'+controlTenantQuery(),
            {
                method:'POST',
                headers:{
                    ...H(),
                    'Content-Type':'application/json'
                },
                body:JSON.stringify(body)
            }
        );

        GUIDED_SQL_PROBE={
            server:body.server,
            database:body.database,
            auth_mode:body.auth_mode,
            username:body.username||'',
            objects:result.objects||[]
        };

        status.innerHTML=
            '<div class="guided-success">'+
            '<b>Conexión correcta.</b> '+
            esc(result.discovered_object_count||0)+
            ' tablas o vistas disponibles para seleccionar.'+
            (
                result.truncated
                    ?' Se muestran los primeros resultados disponibles.'
                    :''
            )+
            '</div>';

        guidedSqlRenderObjects(
            result.objects||[]
        )
    }catch(e){
        GUIDED_SQL_PROBE=null;

        status.innerHTML=
            '<div class="notice error">'+
            esc(e.message)+
            '</div>'
    }finally{
        button.disabled=false;
        button.textContent=
            'Probar conexión y buscar tablas'
    }
}

function guidedSqlSelectedObjects(){
    return Array.from(
        document.querySelectorAll(
            '.gsSqlObject:checked'
        )
    ).map(item=>({
        schema:String(
            item.dataset.schema||''
        ),
        qualified_name:String(
            item.dataset.qualified||''
        )
    }))
}

async function guidedSqlSave(){
    if(!can('sql:configure'))return;

    const secret=controlElement('gsSqlSecret');
    const status=controlElement('gsSqlStatus');
    const save=controlElement('gsSqlSaveBtn');

    try{
        if(!GUIDED_SQL_PROBE){
            throw new Error(
                'Primero prueba la conexión.'
            )
        }

        const current=guidedSqlPayload();

        if(
            current.server!==GUIDED_SQL_PROBE.server ||
            current.database!==GUIDED_SQL_PROBE.database ||
            current.auth_mode!==GUIDED_SQL_PROBE.auth_mode ||
            current.username!==GUIDED_SQL_PROBE.username
        ){
            throw new Error(
                'Los datos cambiaron. Vuelve a probar la conexión.'
            )
        }

        const selected=guidedSqlSelectedObjects();

        if(!selected.length){
            throw new Error(
                'Selecciona al menos una tabla o vista.'
            )
        }

        const schemas=[
            ...new Set(
                selected.map(item=>item.schema)
            )
        ];

        const objects=[
            ...new Set(
                selected.map(item=>item.qualified_name)
            )
        ];

        const display=
            controlElement('gsSqlDisplay').value.trim() ||
            ('SQL Server - '+current.database);

        const body={
            connection_id:guidedSqlConnectionId(),
            display_name:display,
            server:current.server,
            database:current.database,
            auth_mode:current.auth_mode,
            username:current.username,
            allowed_schemas:schemas,
            allowed_tables:objects,
            max_rows:500
        };

        if(current.auth_mode==='SQL_AUTH'){
            body.secret=secret.value
        }

        save.disabled=true;

        await guidedSqlRequest(
            '/api/admin/sql/connections'+controlTenantQuery(),
            {
                method:'POST',
                headers:{
                    ...H(),
                    'Content-Type':'application/json'
                },
                body:JSON.stringify(body)
            }
        );

        status.innerHTML=
            '<div class="guided-success">'+
            '<b>Fuente SQL guardada.</b> '+
            'La empresa sólo podrá consultar los objetos seleccionados.'+
            '</div>';

        toast('Fuente SQL configurada.');

        GUIDED_SQL_PROBE=null;

        controlElement('gsSqlDisplay').value='';
        controlElement('gsSqlServer').value='';
        controlElement('gsSqlDatabase').value='';
        controlElement('gsSqlUsername').value='';
        secret.value='';

        controlElement('gsSqlObjects').innerHTML='';
        controlElement('gsSqlObjects').style.display='none';
        controlElement('gsSqlSelectionActions').style.display='none';

        await Promise.allSettled([
            controlLoadSql(),
            controlLoadReadiness(false)
        ])
    }catch(e){
        status.innerHTML=
            '<div class="notice error">'+
            esc(e.message)+
            '</div>'
    }finally{
        secret.value='';
        guidedSqlSelectionChanged()
    }
}


function controlSqlActions(profile){
    const actions=[];

    if(!CONTROL_SQL_ADVANCED){
        if(can('sql:read')){
            actions.push(
                '<button class="btn" onclick="controlSqlRun(\''+
                esc(profile.connection_id)+
                '\',\'test\')">Comprobar conexión</button>'
            )
        }

        return actions.join(' ')
    }

    if(can('sql:read')){
        actions.push(
            '<button class="btn" onclick="controlSqlRun(\''+
            esc(profile.connection_id)+
            '\',\'test\')">Probar</button>'
        );

        actions.push(
            '<button class="btn" onclick="controlSqlRun(\''+
            esc(profile.connection_id)+
            '\',\'discover\')">Descubrir</button>'
        )
    }

    if(can('sql:configure')){
        actions.push(
            '<button class="btn" onclick="controlEditSql(\''+
            esc(profile.connection_id)+
            '\')">Editar</button>'
        );

        actions.push(
            '<button class="btn" onclick="controlSqlAllowlist(\''+
            esc(profile.connection_id)+
            '\')">Allowlist</button>'
        );

        const action=
            profile.enabled
                ?'disable'
                :'enable';

        const label=
            profile.enabled
                ?'Deshabilitar'
                :'Habilitar';

        actions.push(
            '<button class="btn" onclick="controlSqlRun(\''+
            esc(profile.connection_id)+
            '\',\''+action+'\')">'+
            label+
            '</button>'
        );

        if(profile.auth_mode==='SQL_AUTH'){
            actions.push(
                '<button class="btn muted" onclick="controlRotateSqlSecret(\''+
                esc(profile.connection_id)+
                '\')">Rotar secret</button>'
            )
        }
    }

    return actions.join(' ')
}


function controlRenderSqlTable(){
    const target=controlElement('controlSql');

    if(!target)return;

    if(CONTROL_SQL_ADVANCED){
        target.innerHTML=
            table(
                CONTROL_SQL,
                [
                    ['Conexion','connection_id'],
                    ['Servidor','server'],
                    ['Base','database'],
                    ['Estado','status',(v)=>pill(v)],
                    ['Max filas','max_rows'],
                    [
                        'Secret',
                        'secret_configured',
                        (v)=>v?'Configurado':'N/A'
                    ]
                ],
                controlSqlActions
            );

        return
    }

    target.innerHTML=
        table(
            CONTROL_SQL,
            [
                [
                    'Fuente',
                    'display_name',
                    (v,r)=>esc(
                        v ||
                        r.database ||
                        'SQL Server'
                    )
                ],
                ['Servidor','server'],
                ['Base de datos','database'],
                ['Estado','status',(v)=>pill(v)]
            ],
            controlSqlActions
        )
}


async function controlLoadSql(){
    if(!can('sql:read')){
        controlUnavailable(
            'controlSql',
            'SQL no autorizado.'
        );
        return
    }

    try{
        const data=await api(
            '/api/admin/sql/connections'+
            controlTenantQuery(),
            {headers:H()}
        );

        CONTROL_SQL=data.items||[];

        controlRenderSqlTable()
    }catch(e){
        controlUnavailable(
            'controlSql',
            e.message
        )
    }
}


async function controlCreateSql(){
    if(!can('sql:configure'))return;

    const secret=controlElement('cpSqlSecret');

    try{
        const auth=controlElement('cpSqlAuth').value;

        const body={
            connection_id:controlElement('cpSqlId').value.trim(),
            display_name:controlElement('cpSqlDisplay').value.trim(),
            server:controlElement('cpSqlServer').value.trim(),
            database:controlElement('cpSqlDatabase').value.trim(),
            auth_mode:auth,
            username:controlElement('cpSqlUsername').value.trim(),
            allowed_schemas:controlCsv(
                controlElement('cpSqlSchemas').value
            ),
            allowed_tables:controlCsv(
                controlElement('cpSqlTables').value
            ),
            max_rows:Number(controlElement('cpSqlMaxRows').value||500)
        };

        if(auth==='SQL_AUTH'){
            body.secret=secret.value
        }

        if(
            !body.connection_id ||
            !body.server ||
            !body.database ||
            !body.allowed_schemas.length ||
            !body.allowed_tables.length
        ){
            throw new Error(
                'Conexion, servidor, base y allowlist son obligatorios.'
            )
        }

        if(auth==='SQL_AUTH'&&!body.secret){
            throw new Error('Secret SQL requerido.')
        }

        await api(
            '/api/admin/sql/connections'+controlTenantQuery(),
            {
                method:'POST',
                headers:{...H(),'Content-Type':'application/json'},
                body:JSON.stringify(body)
            }
        );

        controlElement('cpSqlId').value='';
        controlElement('cpSqlDisplay').value='';
        controlElement('cpSqlServer').value='';
        controlElement('cpSqlDatabase').value='';
        controlElement('cpSqlUsername').value='';
        controlElement('cpSqlTables').value='';

        toast('Conexion SQL creada.');
        await controlLoadSql()
    }catch(e){
        toast(e.message,true)
    }finally{
        secret.value=''
    }
}

async function controlEditSql(connectionId){
    const profile=CONTROL_SQL.find(
        x=>x.connection_id===connectionId
    );

    if(!profile||!can('sql:configure'))return;

    const display=prompt(
        'Nombre de la conexion:',
        profile.display_name||''
    );

    if(display===null)return;

    const server=prompt(
        'Servidor:',
        profile.server||''
    );

    if(server===null)return;

    const database=prompt(
        'Base de datos:',
        profile.database||''
    );

    if(database===null)return;

    try{
        await api(
            '/api/admin/sql/connections/'+
            encodeURIComponent(connectionId)+
            controlTenantQuery(),
            {
                method:'PATCH',
                headers:{...H(),'Content-Type':'application/json'},
                body:JSON.stringify({
                    display_name:display,
                    server,
                    database
                })
            }
        );

        toast('Conexion SQL actualizada.');
        await controlLoadSql()
    }catch(e){
        toast(e.message,true)
    }
}

async function controlSqlAllowlist(connectionId){
    const profile=CONTROL_SQL.find(
        x=>x.connection_id===connectionId
    );

    if(!profile||!can('sql:configure'))return;

    const schemas=prompt(
        'Schemas permitidos, separados por coma:',
        (profile.allowed_schemas||[]).join(',')
    );

    if(schemas===null)return;

    const objects=prompt(
        'Objetos permitidos, separados por coma:',
        (profile.allowed_tables||[]).join(',')
    );

    if(objects===null)return;

    try{
        await api(
            '/api/admin/sql/connections/'+
            encodeURIComponent(connectionId)+
            '/allowlist'+controlTenantQuery(),
            {
                method:'PATCH',
                headers:{...H(),'Content-Type':'application/json'},
                body:JSON.stringify({
                    schemas:controlCsv(schemas),
                    objects:controlCsv(objects)
                })
            }
        );

        toast('Allowlist actualizada.');
        await controlLoadSql()
    }catch(e){
        toast(e.message,true)
    }
}

async function controlRotateSqlSecret(connectionId){
    if(!can('sql:configure'))return;

    let secret=prompt('Nuevo secret SQL:');

    if(secret===null)return;

    try{
        if(!secret)throw new Error('Secret SQL requerido.');

        await api(
            '/api/admin/sql/connections/'+
            encodeURIComponent(connectionId)+
            '/secret'+controlTenantQuery(),
            {
                method:'POST',
                headers:{...H(),'Content-Type':'application/json'},
                body:JSON.stringify({secret})
            }
        );

        toast('Secret SQL rotado.');
        await controlLoadSql()
    }catch(e){
        toast(e.message,true)
    }finally{
        secret=''
    }
}

async function controlSqlRun(connectionId,action){
    const configure=['enable','disable'].includes(action);

    if(configure&&!can('sql:configure'))return;
    if(!configure&&!can('sql:read'))return;

    try{
        const result=await api(
            '/api/admin/sql/connections/'+
            encodeURIComponent(connectionId)+
            '/'+action+
            controlTenantQuery(),
            {method:'POST',headers:H()}
        );

        if(action==='discover'){
            const count=
                result.discovered_object_count ??
                (result.objects||[]).length ??
                0;
            toast('Discovery completado. Objetos: '+count)
        }else if(action==='test'){
            toast('Prueba SQL completada.')
        }else{
            toast(
                action==='enable'
                    ?'Conexion habilitada.'
                    :'Conexion deshabilitada.'
            )
        }

        await Promise.allSettled([
            controlLoadSql(),
            controlLoadReadiness(false)
        ])
    }catch(e){
        toast(e.message,true)
    }
}


function controlReadinessStep(name,step){
    const item=step||{};
    const status=String(
        item.status||'BLOCKED'
    ).toUpperCase();

    const required=
        item.required===true
            ?'Requerido'
            :(
                item.required===false
                    ?'Opcional'
                    :''
            );

    let detail='';

    if(item.connection_count!=null){
        detail+=' / conexiones: '+
            esc(item.connection_count)
    }

    if(item.discovered_object_count!=null){
        detail+=' / objetos: '+
            esc(item.discovered_object_count)
    }

    const code=String(item.code||'').trim();
    const safeMessage=String(item.safe_message||'').trim();
    const action=String(item.suggested_action||'').trim();
    const checked=String(item.last_checked_at||'').trim();

    return (
        '<div style="padding:7px 0;border-bottom:1px solid #e5e7eb">'+
        '<b>'+esc(name)+'</b> '+
        '<span class="pill '+esc(status)+'">'+
        esc(status)+
        '</span>'+
        (
            required
                ?' <span class="mutedtxt">'+
                 esc(required)+
                 '</span>'
                :''
        )+
        (
            detail
                ?'<div class="mutedtxt">'+
                 detail+
                 '</div>'
                :''
        )+
        (
            code
                ?'<div class="mutedtxt">Código: '+
                 esc(code)+
                 '</div>'
                :''
        )+
        (
            safeMessage
                ?'<div class="mutedtxt">'+
                 esc(safeMessage)+
                 '</div>'
                :''
        )+
        (
            action
                ?'<div class="mutedtxt">Acción: '+
                 esc(action)+
                 '</div>'
                :''
        )+
        (
            checked
                ?'<div class="mutedtxt">Última evidencia: '+
                 esc(checked)+
                 '</div>'
                :''
        )+
        '</div>'
    )
}

function controlRenderReadiness(payload){
    const readiness=
        payload&&payload.readiness
            ?payload.readiness
            :(payload||{});

    const status=String(
        readiness.status||'BLOCKED'
    ).toUpperCase();

    const verification=String(
        readiness.verification_status||
        'CONFIGURED'
    ).toUpperCase();

    const steps=readiness.steps||{};

    const order=[
        ['Empresa','company'],
        ['Administrador','admin'],
        ['SQL Server','sql'],
        ['IA','ai'],
        ['Branding','branding']
    ];

    let html=
        '<div class="notice">'+
        '<b>Estado general:</b> '+
        '<span class="pill '+esc(status)+'">'+
        esc(status)+
        '</span> '+
        '<span class="mutedtxt">'+
        'Verificacion: '+
        '<span class="pill '+esc(verification)+'">'+
        esc(verification)+
        '</span>'+
        '</span>'+
        '</div>';

    html+=order.map(
        item=>controlReadinessStep(
            item[0],
            steps[item[1]]
        )
    ).join('');

    if(
        payload&&
        payload.ai_test&&
        payload.ai_test.status
    ){
        const aiStatus=String(
            payload.ai_test.status
        ).toUpperCase();

        html+=
            '<div class="mutedtxt" style="margin-top:8px">'+
            'Ultima validacion IA de esta solicitud: '+
            '<span class="pill '+esc(aiStatus)+'">'+
            esc(aiStatus)+
            '</span>'+
            '</div>'
    }

    controlElement(
        'controlReadiness'
    ).innerHTML=html
}

async function controlLoadReadiness(validate=false){
    if(!can('config:read')){
        controlUnavailable(
            'controlReadiness',
            'Preparacion no autorizada.'
        );
        return
    }

    const tenant=controlTenantId();

    if(!tenant){
        controlUnavailable(
            'controlReadiness',
            'Selecciona una empresa.'
        );
        return
    }

    try{
        const endpoint=
            '/api/admin/tenants/'+
            encodeURIComponent(tenant)+
            '/readiness'+
            (
                validate
                    ?'/validate'
                    :''
            );

        const result=await api(
            endpoint,
            {
                method:
                    validate
                        ?'POST'
                        :'GET',
                headers:H()
            }
        );

        controlRenderReadiness(
            result
        );

        if(validate){
            const readiness=
                result.readiness||{};

            toast(
                'Preparacion: '+
                (
                    readiness.status||
                    'sin estado'
                )
            )
        }

        return result
    }catch(e){
        controlUnavailable(
            'controlReadiness',
            e.message
        );

        if(validate){
            toast(
                e.message,
                true
            )
        }
    }
}

async function controlValidateReadiness(){
    return controlLoadReadiness(
        true
    )
}

let GUIDED_AI_TEST=null;

function controlToggleAiAdvanced(){
    const editor=controlElement('cpAiEditor');
    const actions=controlElement('cpAiAdvancedActions');
    const open=editor.style.display==='none';
    editor.style.display=open?'grid':'none';
    actions.style.display=open?'flex':'none';
    controlElement('cpAiAdvancedToggle').textContent=
        open?'Ocultar configuración avanzada':'Configuración avanzada';
}

function guidedAiChoice(){
    const selected=document.querySelector('input[name="gsAiChoice"]:checked');
    return selected?selected.value:'DISABLED';
}

function guidedAiFingerprint(provider){return JSON.stringify(provider)}

function guidedAiRenderStatus(message,status='NOT_CONFIGURED'){
    const target=controlElement('gsAiStatus');
    if(!target)return;
    target.innerHTML='<div class="notice"><span class="pill '+esc(status)+'">'+
        esc(status)+'</span> '+esc(message)+'</div>';
}

function guidedAiInvalidate(){
    GUIDED_AI_TEST=null;
    if(controlElement('gsAiStatus'))guidedAiRenderStatus(
        'La configuración cambió. Prueba la IA antes de guardarla.',
        'NOT_CONFIGURED'
    );
}

function aiModelOption(select,value,label,disabled=false){
    const option=document.createElement('option');
    option.value=value;option.textContent=label;option.disabled=disabled;
    select.appendChild(option);
    return option;
}

function aiModelSelectState(selectId,provider,result,configured){
    const select=controlElement(selectId);
    if(!select)return;
    select.innerHTML='';
    const status=String((result&&result.status)||'UNAVAILABLE').toUpperCase();
    if(provider.provider_type==='DISABLED'){
        aiModelOption(select,'','La IA está desactivada');select.disabled=true;return;
    }
    const models=Array.isArray(result&&result.models)?result.models:[];
    if(status==='PASS'){
        aiModelOption(select,'','Selecciona un modelo');
        models.forEach(item=>aiModelOption(select,String(item.id),String(item.name||item.id)));
        select.disabled=false;
    }else if(status==='EMPTY'){
        aiModelOption(select,'','No se encontraron modelos instalados');select.disabled=true;
    }else if(status==='UNSUPPORTED'){
        aiModelOption(select,'','Este proveedor no permite descubrimiento todavía');select.disabled=true;
    }else{
        aiModelOption(select,'','No fue posible conectar con el proveedor');select.disabled=true;
    }
    if(configured){
        const present=[...select.options].some(option=>option.value===configured);
        if(!present)aiModelOption(select,configured,configured+' — configurado, no disponible actualmente',true);
        select.value=configured;
    }
}

async function controlLoadAiModels(provider){
    const configured=String(provider.model||'').trim();
    const selects=['cpAiModel','gsAiModel'];
    selects.forEach(id=>{const select=controlElement(id);if(select){select.innerHTML='';aiModelOption(select,'','Cargando modelos…');select.disabled=true}});
    if(provider.provider_type==='DISABLED'){
        selects.forEach(id=>aiModelSelectState(id,provider,{status:'DISABLED'},configured));return;
    }
    const tenant=controlTenantId();
    if(!tenant){selects.forEach(id=>aiModelSelectState(id,provider,{status:'UNAVAILABLE'},configured));return;}
    try{
        const result=await api('/api/admin/ai/provider/models',{
            method:'POST',headers:{...H(),'Content-Type':'application/json'},
            body:JSON.stringify({tenant_id:tenant,provider})
        });
        selects.forEach(id=>aiModelSelectState(id,provider,result,configured));
    }catch(e){
        selects.forEach(id=>aiModelSelectState(id,provider,{status:'UNAVAILABLE'},configured));
        guidedAiRenderStatus('No fue posible conectar con el proveedor de modelos.','BLOCKED');
    }
}

function guidedAiProvider(){
    const type=guidedAiChoice();
    if(type==='DISABLED')return {
        provider_id:'disabled',provider_type:'DISABLED',enabled:false,timeout:30
    };
    const technical=controlAiFromForm();
    return {
        provider_id:type.toLowerCase(),provider_type:type,
        base_url:technical.base_url||
            (type==='OLLAMA'?'http://127.0.0.1:11434':'http://127.0.0.1:1234/v1'),
        model:controlElement('gsAiModel').value.trim()||technical.model||null,
        enabled:true,timeout:Number(technical.timeout||30),
        context_window:technical.context_window||null
    }
}

function guidedAiSyncAdvanced(provider){
    controlElement('cpAiType').value=provider.provider_type;
    controlElement('cpAiUrl').value=provider.base_url||'';
    controlElement('cpAiModel').value=provider.model||'';
    controlElement('cpAiTimeout').value=provider.timeout||30;
    controlElement('cpAiContext').value=provider.context_window||'';
    controlElement('cpAiEnabled').value=String(Boolean(provider.enabled));
}

function guidedAiSelectionChanged(){
    const type=guidedAiChoice();
    controlElement('gsAiModelWrap').style.display=type==='DISABLED'?'none':'block';
    if(type==='DISABLED')controlElement('gsAiModel').value='';
    const provider=guidedAiProvider();
    guidedAiSyncAdvanced(provider);
    controlLoadAiModels(provider);
    guidedAiInvalidate();
}

function guidedAiApplyProvider(provider){
    const type=(provider&&provider.provider_type)||'DISABLED';
    const choice=document.querySelector('input[name="gsAiChoice"][value="'+type+'"]')||
        document.querySelector('input[name="gsAiChoice"][value="DISABLED"]');
    choice.checked=true;
    controlElement('gsAiModel').value=(provider&&provider.model)||'';
    guidedAiSyncAdvanced(provider||{provider_type:'DISABLED',enabled:false,timeout:30});
    controlElement('gsAiModelWrap').style.display=
        choice.value==='DISABLED'?'none':'block';
    controlLoadAiModels(provider||{provider_type:'DISABLED',enabled:false,timeout:30});
}

async function guidedAiTest(){
    if(!can('config:read'))return;
    const tenant=controlTenantId();
    if(!tenant){toast('Empresa requerida.',true);return}
    const provider=guidedAiProvider();
    try{
        const result=await api('/api/admin/ai/provider/test',{
            method:'POST',headers:{...H(),'Content-Type':'application/json'},
            body:JSON.stringify({tenant_id:tenant,provider})
        });
        const status=String(result.status||'BLOCKED').toUpperCase();
        GUIDED_AI_TEST={fingerprint:guidedAiFingerprint(provider),status,result};
        guidedAiRenderStatus(
            status==='PASS'||status==='DISABLED'
                ?'La prueba terminó correctamente.'
                :'La prueba no confirmó disponibilidad.',status
        );
    }catch(e){GUIDED_AI_TEST=null;guidedAiRenderStatus(e.message,'BLOCKED')}
}

async function guidedAiSave(){
    if(!can('config:write'))return;
    const tenant=controlTenantId();
    if(!tenant){toast('Empresa requerida.',true);return}
    const provider=guidedAiProvider();
    const tested=GUIDED_AI_TEST&&
        GUIDED_AI_TEST.fingerprint===guidedAiFingerprint(provider)&&
        ['PASS','DISABLED'].includes(GUIDED_AI_TEST.status);
    if(provider.provider_type!=='DISABLED'&&!tested){
        guidedAiRenderStatus('Primero prueba la IA con la configuración actual.','BLOCKED');
        return;
    }
    try{
        const current=await api('/api/admin/tenants/'+encodeURIComponent(tenant)+'/config',{headers:H()});
        const features={...((current.effective&&current.effective.enabled_features)||{}),
            ai_enabled:Boolean(provider.enabled)};
        await api('/api/admin/tenants/'+encodeURIComponent(tenant)+'/config',{
            method:'PATCH',headers:{...H(),'Content-Type':'application/json'},
            body:JSON.stringify({ai_provider:provider,enabled_features:features})
        });
        guidedAiRenderStatus(
            provider.provider_type==='DISABLED'
                ?'La empresa continuará sin IA.'
                :'Configuración IA guardada.',
            provider.provider_type==='DISABLED'?'DISABLED':'CONFIGURED'
        );
        await Promise.allSettled([controlLoadAi(),controlLoadReadiness(false)]);
    }catch(e){guidedAiRenderStatus(e.message,'BLOCKED')}
}

async function guidedAiValidateReadiness(){
    const result=await controlValidateReadiness();
    const readiness=(result&&result.readiness)||{};
    const status=String(readiness.status||'BLOCKED').toUpperCase();
    guidedAiRenderStatus(
        status==='READY'
            ?'Listo: la preparación fue confirmada por el servidor.'
            :'La preparación aún no está lista. Revisa los pasos indicados.',status
    );
}

function controlInitializeGuidedAi(){
    if(controlElement('guidedAiCard'))return;
    const editor=controlElement('cpAiEditor');
    if(!editor)return;
    const advanced=editor.closest('.card');
    advanced.querySelector('h3').textContent='Proveedor de IA — configuración avanzada';
    editor.style.display='none';
    [...advanced.querySelectorAll('button')].forEach(button=>button.style.display='none');
    const toggle=document.createElement('button');
    toggle.id='cpAiAdvancedToggle';toggle.className='btn muted advanced-ai-toggle';
    toggle.setAttribute('data-cp-permission','config:read');
    toggle.textContent='Configuración avanzada';toggle.onclick=controlToggleAiAdvanced;
    advanced.insertBefore(toggle,editor);
    const actions=document.createElement('div');
    actions.id='cpAiAdvancedActions';actions.className='row';actions.style.display='none';
    actions.innerHTML='<button class="btn" data-cp-permission="config:read" onclick="controlTestAi()">Probar proveedor</button> <button class="btn ok" data-cp-permission="config:write" onclick="controlSaveAi()">Guardar proveedor</button>';
    advanced.appendChild(actions);
    const guided=document.createElement('div');
    guided.id='guidedAiCard';guided.className='card guided-ai';
    guided.setAttribute('data-cp-permission','config:read');
    guided.innerHTML='<h3>Configurar inteligencia artificial</h3><div class="mutedtxt">Elige cómo asistirá la IA local a esta empresa. Puedes continuar sin IA y activarla después.</div><div class="guided-ai-choice"><label><input type="radio" name="gsAiChoice" value="OLLAMA" onchange="guidedAiSelectionChanged()">Ollama local</label><label><input type="radio" name="gsAiChoice" value="OPENAI_COMPATIBLE_LOCAL" onchange="guidedAiSelectionChanged()">Servidor local compatible</label><label><input type="radio" name="gsAiChoice" value="DISABLED" checked onchange="guidedAiSelectionChanged()">Continuar sin IA</label></div><div class="formgrid"><label id="gsAiModelWrap" style="display:none">Modelo<select id="gsAiModel" onchange="guidedAiInvalidate()"><option value="">Cargando modelos…</option></select></label></div><div class="row"><button id="gsAiTestBtn" class="btn" data-cp-permission="config:read" onclick="guidedAiTest()">Probar IA</button><button id="gsAiSaveBtn" class="btn ok" data-cp-permission="config:write" onclick="guidedAiSave()">Guardar y continuar</button><button id="gsAiValidateBtn" class="btn muted" data-cp-permission="config:read" onclick="guidedAiValidateReadiness()">Validar preparación</button></div><div id="gsAiStatus" class="guided-ai-status"></div>';
    advanced.parentNode.insertBefore(guided,advanced);
    controlApplyCapabilities();
}

function controlAiFromForm(){
    const type=controlElement('cpAiType').value;

    if(type==='DISABLED'){
        return {
            provider_id:'disabled',
            provider_type:'DISABLED',
            enabled:false,
            timeout:30
        }
    }

    const contextRaw=controlElement('cpAiContext').value.trim();

    return {
        provider_id:type.toLowerCase(),
        provider_type:type,
        base_url:controlElement('cpAiUrl').value.trim(),
        model:controlElement('cpAiModel').value.trim()||null,
        enabled:controlElement('cpAiEnabled').value==='true',
        timeout:Number(controlElement('cpAiTimeout').value||30),
        context_window:contextRaw?Number(contextRaw):null
    }
}

function controlAiProviderChanged(){
    const provider=controlAiFromForm();
    controlLoadAiModels(provider);
    guidedAiInvalidate();
}

function controlRenderAi(provider){
    const p=provider||{
        provider_type:'DISABLED',
        enabled:false,
        timeout:30
    };

    controlElement('cpAiType').value=
        p.provider_type||'DISABLED';

    controlElement('cpAiUrl').value=
        p.base_url||'';

    controlElement('cpAiModel').value=
        p.model||'';

    controlElement('cpAiTimeout').value=
        p.timeout||30;

    controlElement('cpAiContext').value=
        p.context_window||'';

    controlElement('cpAiEnabled').value=
        String(Boolean(p.enabled));

    if(controlElement('guidedAiCard')){
        guidedAiApplyProvider(p);
        guidedAiRenderStatus(
            p.provider_type==='DISABLED'
                ?'La empresa está configurada para continuar sin IA.'
                :'Configuración actual cargada.',
            p.provider_type==='DISABLED'?'DISABLED':'CONFIGURED'
        );
    }

    controlElement('controlAi').innerHTML=
        '<pre>'+
        esc(JSON.stringify({
            provider_id:p.provider_id,
            provider_type:p.provider_type,
            base_url:p.base_url,
            model:p.model,
            enabled:p.enabled,
            timeout:p.timeout,
            context_window:p.context_window
        },null,2))+
        '</pre>'
}

async function controlLoadAi(){
    if(!can('config:read')){
        controlUnavailable(
            'controlAi',
            'Configuracion IA no autorizada.'
        );
        return
    }

    try{
        let url='/api/admin/ai/providers';

        const tenant=controlTenantId();

        if(tenant){
            url+='?tenant_id='+encodeURIComponent(tenant)
        }

        const data=await api(url,{headers:H()});

        controlRenderAi(data.provider)
    }catch(e){
        controlUnavailable('controlAi',e.message)
    }
}

async function controlTestAi(){
    if(!can('config:read'))return;

    const tenant=controlTenantId();

    if(!tenant){
        toast('Empresa requerida.',true);
        return
    }

    try{
        const provider=controlAiFromForm();

        const result=await api(
            '/api/admin/ai/provider/test',
            {
                method:'POST',
                headers:{...H(),'Content-Type':'application/json'},
                body:JSON.stringify({
                    tenant_id:tenant,
                    provider
                })
            }
        );

        toast(
            'Proveedor IA: '+
            (result.status||'sin estado')+
            (
                result.latency_ms!=null
                    ?' / '+result.latency_ms+' ms'
                    :''
            )
        )
    }catch(e){
        toast(e.message,true)
    }
}

async function controlSaveAi(){
    if(!can('config:write'))return;

    const tenant=controlTenantId();

    if(!tenant){
        toast('Empresa requerida.',true);
        return
    }

    try{
        const provider=controlAiFromForm();

        const current=await api(
            '/api/admin/tenants/'+
            encodeURIComponent(tenant)+
            '/config',
            {headers:H()}
        );

        const enabledFeatures={
            ...((current.effective&&
                current.effective.enabled_features)||{}),
            ai_enabled:Boolean(provider.enabled)
        };

        await api(
            '/api/admin/tenants/'+
            encodeURIComponent(tenant)+
            '/config',
            {
                method:'PATCH',
                headers:{...H(),'Content-Type':'application/json'},
                body:JSON.stringify({
                    ai_provider:provider,
                    enabled_features:enabledFeatures
                })
            }
        );

        toast('Proveedor IA guardado.');
        await Promise.allSettled([
            controlLoadAi(),
            controlLoadReadiness(false)
        ])
    }catch(e){
        toast(e.message,true)
    }
}


function maintenanceStatus(message){
    const el=document.getElementById('maintenanceStatus');
    if(el)el.textContent=String(message||'')
}

function maintenanceStatusLabel(value){
    const map={
        QUEUED:'En cola',
        UPLOADING:'Recibiendo respaldo',
        STOPPING:'Deteniendo servicio',
        VALIDATING:'Validando respaldo',
        BACKING_UP:'Creando respaldo',
        RESTORING:'Restaurando',
        STARTING:'Iniciando servicio',
        VERIFYING:'Validando servicio',
        COMPLETED:'Completado',
        FAILED:'Falló'
    };
    return map[String(value||'')]||String(value||'N/D')
}

function renderMaintenanceJobs(items){
    const host=document.getElementById('maintenanceJobs');
    if(!host)return;
    const rows=Array.isArray(items)?items:[];
    if(!rows.length){
        host.innerHTML='<div class="empty">Sin operaciones de mantenimiento.</div>';
        return
    }
    host.innerHTML='<table><thead><tr><th>Operación</th><th>Estado</th><th>Fecha</th><th>Resultado</th><th>Acciones</th></tr></thead><tbody>'+
        rows.map(job=>{
            const operation=job.operation==='restore'?'Restauración':'Respaldo';
            const status=maintenanceStatusLabel(job.status);
            const result=job.error_code?esc(job.error_code):(job.status==='COMPLETED'?'OK':'');
            const download=(
                job.operation==='backup'&&
                job.status==='COMPLETED'&&
                job.download_ready
            )?'<button class="btn" onclick="maintenanceDownload(\''+
                esc(job.job_id)+'\')">Descargar</button>':'';
            return '<tr><td>'+esc(operation)+'</td><td>'+esc(status)+'</td><td>'+
                esc(job.updated_at||job.created_at||'')+'</td><td>'+result+
                '</td><td>'+download+'</td></tr>'
        }).join('')+'</tbody></table>'
}

async function loadMaintenanceJobs(){
    if(!controlSystemAdmin()||!can('backup:create'))return;
    maintenanceStatus('Consultando operaciones...');
    try{
        const response=await fetch(
            '/api/admin/maintenance/jobs',
            {headers:H()}
        );
        if(response.status===401){
            showLogin('La sesión expiró o fue revocada.');
            return
        }
        let payload={};
        try{payload=await response.json()}catch{}
        if(!response.ok){
            throw new Error(
                (payload.detail&&payload.detail.message)||
                'No se pudieron consultar las operaciones.'
            )
        }
        renderMaintenanceJobs(payload.items||[]);
        maintenanceStatus('Operaciones actualizadas.')
    }catch(e){
        maintenanceStatus(
            'El servicio puede estar reiniciándose. Usa Actualizar operaciones cuando vuelva a estar disponible.'
        )
    }
}

async function maintenanceCreateBackup(){
    if(!controlSystemAdmin()||!can('backup:create'))return;
    if(!confirm('El servicio local se reiniciará brevemente para crear un respaldo consistente. ¿Continuar?'))return;
    maintenanceStatus('Programando respaldo...');
    try{
        const response=await fetch(
            '/api/admin/maintenance/backup',
            {
                method:'POST',
                headers:H()
            }
        );
        let payload={};
        try{payload=await response.json()}catch{}
        if(response.status===401){
            showLogin('La sesión expiró o fue revocada.');
            return
        }
        if(!response.ok){
            const detail=payload.detail||{};
            throw new Error(
                detail.message||
                detail.code||
                'No se pudo iniciar el respaldo.'
            )
        }
        maintenanceStatus(
            'Respaldo iniciado. El servicio se reiniciará brevemente. Después usa Actualizar operaciones.'
        );
        renderMaintenanceJobs([payload])
    }catch(e){
        toast(e.message||'No se pudo iniciar el respaldo.',true)
    }
}

async function maintenanceRestore(){
    if(!controlSystemAdmin()||!can('backup:restore'))return;
    const input=document.getElementById('maintenanceRestoreFile');
    const confirmValue=String(
        document.getElementById('maintenanceRestoreConfirm').value||''
    ).trim();
    const file=input&&input.files?input.files[0]:null;
    if(!file){
        toast('Selecciona el archivo ZIP de respaldo.',true);
        return
    }
    if(confirmValue!=='RESTAURAR'){
        toast('Escribe RESTAURAR para confirmar la recuperación.',true);
        return
    }
    if(!confirm('La restauración reemplazará el estado persistente administrado y reiniciará el servicio. ¿Continuar?'))return;
    maintenanceStatus('Validando y programando restauración...');
    const form=new FormData();
    form.append('file',file);
    try{
        const response=await fetch(
            '/api/admin/maintenance/restore',
            {
                method:'POST',
                headers:H(),
                body:form
            }
        );
        let payload={};
        try{payload=await response.json()}catch{}
        if(response.status===401){
            showLogin('La sesión expiró o fue revocada.');
            return
        }
        if(!response.ok){
            const detail=payload.detail||{};
            throw new Error(
                detail.message||
                detail.code||
                'No se pudo iniciar la restauración.'
            )
        }
        input.value='';
        document.getElementById('maintenanceRestoreConfirm').value='';
        maintenanceStatus(
            'Respaldo validado. La restauración comenzó y el servicio se reiniciará. Es posible que debas iniciar sesión nuevamente con las credenciales restauradas.'
        );
        renderMaintenanceJobs([payload])
    }catch(e){
        toast(e.message||'No se pudo iniciar la restauración.',true)
    }
}

async function maintenanceDownload(jobId){
    if(!controlSystemAdmin()||!can('backup:create'))return;
    try{
        const response=await fetch(
            '/api/admin/maintenance/jobs/'+
            encodeURIComponent(jobId)+
            '/download',
            {headers:H()}
        );
        if(response.status===401){
            showLogin('La sesión expiró o fue revocada.');
            return
        }
        if(!response.ok){
            let payload={};
            try{payload=await response.json()}catch{}
            const detail=payload.detail||{};
            throw new Error(
                detail.message||
                detail.code||
                'El respaldo no está disponible.'
            )
        }
        const blob=await response.blob();
        if(!blob.size)throw new Error('El respaldo está vacío.');
        const url=URL.createObjectURL(blob);
        const link=document.createElement('a');
        link.href=url;
        link.download='IA_EMPRESARIAL_LOCAL_backup_'+String(jobId)+'.zip';
        link.click();
        setTimeout(()=>URL.revokeObjectURL(url),0)
    }catch(e){
        toast(e.message||'No se pudo descargar el respaldo.',true)
    }
}

async function loadControlPlane(){
    controlInitializeGuidedAi();
    const jobs=[];

    if(can('config:read')){
        jobs.push(controlLoadOverview());
        jobs.push(controlLoadAi());
        jobs.push(controlLoadReadiness(false))
    }else{
        controlUnavailable(
            'controlSummary',
            'Resumen no autorizado.'
        );
        controlUnavailable(
            'controlAi',
            'Configuracion IA no autorizada.'
        );
        controlUnavailable(
            'controlReadiness',
            'Preparacion no autorizada.'
        )
    }

    if(can('tenant:list')){
        jobs.push(controlLoadTenants())
    }else{
        controlUnavailable(
            'controlTenants',
            'Empresas no autorizadas.'
        )
    }

    if(can('user:list')){
        jobs.push(controlLoadUsers())
    }else{
        controlUnavailable(
            'controlUsers',
            'Usuarios no autorizados.'
        )
    }

    if(can('sql:read')){
        jobs.push(controlLoadSql())
    }else{
        controlUnavailable(
            'controlSql',
            'SQL no autorizado.'
        )
    }

    await Promise.allSettled(jobs);

    controlApplyCapabilities()
}
function renderOverview(o){const c=o.counts||{};document.getElementById('metrics').innerHTML=[['Memorias',c.memories],['Documentos',c.documents],['Reglas',c.rules],['Definiciones',c.semantic_definitions],['Feedback pendiente',c.feedback_pending],['Trazas',c.traces],['Datasets',c.datasets],['Conflictos',c.conflicts]].map(x=>'<div class="metric"><span class="mutedtxt">'+esc(x[0])+'</span><b>'+esc(x[1]??0)+'</b></div>').join('');document.getElementById('statusSummary').innerHTML=table(o.statuses||[],[['Tipo','type'],['Estado','status',(v)=>pill(v)],['Cantidad','count']])}
function renderMem(rows){document.getElementById('memoryTable').innerHTML=table(rows,[['Categoría','category'],['Contenido','content'],['Confianza','confidence'],['Confirmada','confirmed',(v)=>v?'Sí':'No'],['Activa','active',(v)=>v?'Sí':'No']],r=>'<button class="btn ok" onclick="confirmMem(\''+r.id+'\')">Confirmar</button> <button class="btn danger" onclick="deleteMem(\''+r.id+'\')">Desactivar</button>')}
function renderDocs(rows){document.getElementById('docsTable').innerHTML=table(rows,[['Documento','name'],['Versión','current_version'],['Chunks','chunk_count'],['Estado','active',(v)=>v?'Activo':'Inactivo']],r=>'<button class="btn" onclick="reindexDoc(\''+r.id+'\')">Reindexar</button> <button class="btn danger" onclick="deleteDoc(\''+r.id+'\')">Eliminar</button>')}
function renderSem(rows){document.getElementById('semanticTable').innerHTML=table(rows,[['Físico','physical_name'],['Semántico','semantic_name'],['Área','area'],['Estado','status',(v)=>pill(v)],['Versión','version'],['Vigencia','valid_from',(v,r)=>esc((v||'∞')+' → '+(r.valid_to||'∞'))]],r=>r.status==='PROPUESTO'?'<button class="btn ok" onclick="validateSem(\''+r.id+'\')">Validar</button> <button class="btn danger" onclick="rejectSem(\''+r.id+'\')">Rechazar</button>':'')}
function renderRules(rows){document.getElementById('rulesTable').innerHTML=table(rows,[['Nombre','name'],['Área','area'],['Expresión','expression'],['Estado','status',(v)=>pill(v)],['Versión','version'],['Vigencia','valid_from',(v,r)=>esc((v||'∞')+' → '+(r.valid_to||'∞'))]],r=>r.status==='PROPUESTO'?'<button class="btn ok" onclick="validateRule(\''+r.id+'\')">Validar</button> <button class="btn danger" onclick="rejectRule(\''+r.id+'\')">Rechazar</button>':(r.status==='VALIDADO'?'<button class="btn warn" onclick="obsoleteRule(\''+r.id+'\')">Obsoletar</button>':''))}
function renderAnalytic(rows){document.getElementById('analyticTable').innerHTML=table(rows,[['Regla','rule_name'],['Tipo','rule_type'],['Target','target'],['Prioridad','priority'],['Estado regla','rule_status',(v)=>pill(v)]])}
function renderFeedback(rows){document.getElementById('feedbackTable').innerHTML=table(rows,[['Tipo','feedback_type'],['Corrección','correction'],['Propuesta','proposal_type'],['Estado','proposal_status',(v)=>pill(v)],['Fecha','created_at']],r=>r.proposal_status==='PROPUESTO'?'<button class="btn ok" onclick="validateFeedback(\''+r.id+'\')">Validar</button> <button class="btn danger" onclick="rejectFeedback(\''+r.id+'\')">Rechazar</button>':'')}
function renderTraces(rows){document.getElementById('traceTable').innerHTML=table(rows,[['Tipo','trace_type'],['Prompt','prompt_preview'],['Estado','status'],['Fecha','created_at']],r=>'<button class="btn" onclick="explainTrace(\''+r.id+'\')">Explicar</button>')}
async function createMemory(){try{await api('/api/enterprise/memories',{method:'POST',headers:J(),body:JSON.stringify({content:memText.value,category:memCategory.value,scope:'company'})});toast('Memoria creada');refreshAll()}catch(e){toast(e.message,true)}}
async function confirmMem(id){try{await api('/api/enterprise/memories/'+id+'/confirm',{method:'POST',headers:H()});refreshAll()}catch(e){toast(e.message,true)}}async function deleteMem(id){try{await api('/api/enterprise/memories/'+id,{method:'DELETE',headers:H()});refreshAll()}catch(e){toast(e.message,true)}}
async function uploadDoc(){try{const f=docFile.files[0];if(!f)throw new Error('Selecciona un archivo');const fd=new FormData();fd.append('file',f);fd.append('scope','company');await api('/api/enterprise/documents',{method:'POST',headers:H(),body:fd});toast('Documento indexado');refreshAll()}catch(e){toast(e.message,true)}}async function reindexDoc(id){try{await api('/api/enterprise/documents/'+id+'/reindex',{method:'POST',headers:H()});refreshAll()}catch(e){toast(e.message,true)}}async function deleteDoc(id){try{await api('/api/enterprise/documents/'+id,{method:'DELETE',headers:H()});refreshAll()}catch(e){toast(e.message,true)}}
async function proposeSemantic(){try{await api('/api/enterprise/semantic-definitions',{method:'POST',headers:J(),body:JSON.stringify({physical_name:semPhysical.value,semantic_name:semName.value,area:semArea.value||null,description:semDesc.value||null})});refreshAll()}catch(e){toast(e.message,true)}}async function validateSem(id){try{await api('/api/enterprise/semantic-definitions/'+id+'/validate',{method:'POST',headers:J(),body:'{}'});refreshAll()}catch(e){if(confirm(e.message+'\n¿Deseas reemplazar conflictos validados?')){await api('/api/enterprise/semantic-definitions/'+id+'/validate',{method:'POST',headers:J(),body:JSON.stringify({replace_conflicts:true})});refreshAll()}}}async function rejectSem(id){await api('/api/enterprise/semantic-definitions/'+id+'/reject',{method:'POST',headers:H()});refreshAll()}
async function proposeRule(){try{await api('/api/enterprise/business-rules',{method:'POST',headers:J(),body:JSON.stringify({name:ruleName.value,area:ruleArea.value||null,expression:ruleExpression.value,description:ruleDesc.value||null})});refreshAll()}catch(e){toast(e.message,true)}}async function validateRule(id){try{await api('/api/enterprise/business-rules/'+id+'/validate',{method:'POST',headers:J(),body:'{}'});refreshAll()}catch(e){if(confirm(e.message+'\n¿Deseas reemplazar conflictos validados?')){await api('/api/enterprise/business-rules/'+id+'/validate',{method:'POST',headers:J(),body:JSON.stringify({replace_conflicts:true})});refreshAll()}}}async function rejectRule(id){await api('/api/enterprise/business-rules/'+id+'/reject',{method:'POST',headers:H()});refreshAll()}async function obsoleteRule(id){await api('/api/enterprise/business-rules/'+id+'/obsolete',{method:'POST',headers:H()});refreshAll()}
async function bindAnalytic(){try{await api('/api/enterprise/rules/'+bindRule.value+'/bind',{method:'POST',headers:J(),body:JSON.stringify({rule_type:bindType.value,target:bindTarget.value,priority:Number(bindPriority.value||100),scope:'company'})});refreshAll()}catch(e){toast(e.message,true)}}
async function validateFeedback(id){try{await api('/api/enterprise/feedback/'+id+'/validate',{method:'POST',headers:J(),body:'{}'});refreshAll()}catch(e){toast(e.message,true)}}async function rejectFeedback(id){await api('/api/enterprise/feedback/'+id+'/reject',{method:'POST',headers:H()});refreshAll()}
async function explainTrace(id){try{const d=await api('/api/enterprise/traces/'+id+'/explain',{headers:H()});document.getElementById('traceExplain').innerHTML='<pre>'+esc(d.explanation||JSON.stringify(d,null,2))+'</pre>'}catch(e){toast(e.message,true)}}
async function loadHistory(){try{const d=await api('/api/enterprise/knowledge/'+encodeURIComponent(histType.value)+'/'+encodeURIComponent(histId.value)+'/history',{headers:H()});historyOut.innerHTML='<pre>'+esc(JSON.stringify(d,null,2))+'</pre>'}catch(e){toast(e.message,true)}}
async function loadAudit(){try{const d=await api('/api/enterprise/audit?limit=100',{headers:H()});document.getElementById('auditTable').innerHTML=table(d.events,[['Evento','event_type'],['Objeto','object_type'],['Resultado','outcome'],['Fecha','created_at']])}catch(e){document.getElementById('auditTable').innerHTML='<div class="empty">Auditoría disponible solo para administrador.</div>'}}
document.querySelectorAll('#nav button').forEach(b=>b.onclick=()=>{document.querySelectorAll('#nav button').forEach(x=>x.classList.remove('active'));document.querySelectorAll('.panel').forEach(x=>x.classList.remove('active'));b.classList.add('active');document.getElementById(b.dataset.p).classList.add('active');if(b.dataset.p==='controlplane')loadControlPlane();if(b.dataset.p==='recuperacion')loadMaintenanceJobs()});if(token){establishSession().then(ok=>{if(ok)refreshAll()})}else showLogin();
</script></body></html>'''
