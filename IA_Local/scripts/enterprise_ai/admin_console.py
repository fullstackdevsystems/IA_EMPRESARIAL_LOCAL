from __future__ import annotations

UNIFIED_ADMIN_HTML = r'''<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>IA Empresarial Local - Administración</title>
<style>
:root{--bg:#f4f7fb;--card:#fff;--ink:#142033;--muted:#64748b;--line:#dbe3ee;--blue:#2563eb;--green:#15803d;--red:#b91c1c;--amber:#b45309;--nav:#0f172a}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font-family:Segoe UI,Arial,sans-serif}.layout{display:grid;grid-template-columns:250px 1fr;min-height:100vh}.side{background:var(--nav);color:#fff;padding:20px 14px}.brand{font-weight:800;font-size:18px;margin:4px 8px 22px}.nav button{width:100%;border:0;background:transparent;color:#cbd5e1;text-align:left;padding:11px 12px;border-radius:9px;margin:2px 0;cursor:pointer}.nav button.active,.nav button:hover{background:#1e293b;color:#fff}.main{padding:24px;min-width:0}.top{display:flex;justify-content:space-between;gap:16px;align-items:center}.links a{margin-left:12px;color:var(--blue);text-decoration:none}.grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:18px 0}.metric,.card{background:var(--card);border:1px solid var(--line);border-radius:14px;box-shadow:0 6px 22px #2342a30c}.metric{padding:15px}.metric b{font-size:24px;display:block;margin-top:4px}.card{padding:18px;margin:14px 0}.panel{display:none}.panel.active{display:block}.row{display:flex;gap:8px;align-items:center;flex-wrap:wrap}input,select,textarea{border:1px solid #cbd5e1;border-radius:8px;padding:8px;width:100%;font:inherit}textarea{min-height:75px}.btn{border:0;border-radius:8px;padding:8px 11px;background:var(--blue);color:#fff;cursor:pointer}.btn.ok{background:var(--green)}.btn.warn{background:var(--amber)}.btn.danger{background:var(--red)}.btn.muted{background:#64748b}.table{overflow:auto}.table table{width:100%;border-collapse:collapse;font-size:13px}.table th,.table td{text-align:left;padding:9px;border-bottom:1px solid #e5e7eb;vertical-align:top}.pill{display:inline-block;padding:3px 7px;border-radius:999px;background:#e2e8f0;font-size:11px}.pill.VALIDADO{background:#dcfce7;color:#166534}.pill.PROPUESTO{background:#fef3c7;color:#92400e}.pill.RECHAZADO,.pill.OBSOLETO{background:#fee2e2;color:#991b1b}.mutedtxt{color:var(--muted);font-size:12px}.notice{background:#eff6ff;border:1px solid #bfdbfe;border-radius:10px;padding:10px;margin:12px 0}.error{background:#fef2f2;border-color:#fecaca}.formgrid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.actions{white-space:nowrap}.empty{padding:18px;color:var(--muted)}pre{white-space:pre-wrap;background:#0f172a;color:#e2e8f0;padding:12px;border-radius:10px;max-height:420px;overflow:auto}@media(max-width:950px){.layout{grid-template-columns:1fr}.side{position:sticky;top:0;z-index:5;padding:10px}.brand{margin:0 8px 8px}.nav{display:flex;overflow:auto}.nav button{width:auto;white-space:nowrap}.grid{grid-template-columns:repeat(2,1fr)}.formgrid{grid-template-columns:1fr}}
</style></head><body>
<div class="layout"><aside class="side"><div class="brand">IA Empresarial Local<br><span style="font-size:11px;font-weight:400;color:#94a3b8">R10.10 Administración Unificada</span></div><div class="nav" id="nav">
<button data-p="resumen" class="active">Resumen</button><button data-p="controlplane">Plataforma</button><button data-p="memoria">Memoria</button><button data-p="documentos">Documentos / RAG</button><button data-p="semantica">Diccionario</button><button data-p="reglas">Reglas empresariales</button><button data-p="analiticas">Reglas analíticas</button><button data-p="feedback">Feedback</button><button data-p="trazas">Trazabilidad</button><button data-p="historial">Historial</button><button data-p="auditoria">Auditoría</button></div></aside>
<main class="main"><div class="top"><div><h2 style="margin:0">Administración empresarial</h2><div class="mutedtxt">Conocimiento, gobernanza, aprendizaje y trazabilidad en una sola consola.</div></div><div class="links"><a id="assistant" href="/assistant">Asistente</a><a href="/">Analizador</a><button class="btn muted" onclick="enterpriseLogout()">Cerrar sesión</button></div></div><div id="auth" class="notice error" style="display:none"></div><div id="msg"></div>
<section id="resumen" class="panel active"><div class="grid" id="metrics"></div><div class="card"><h3>Estado de conocimiento</h3><div id="statusSummary"></div></div></section>
<section id="controlplane" class="panel"><div class="card"><h3>Enterprise Control Plane</h3><div class="mutedtxt">Administracion gobernada de empresa, usuarios, SQL Server e IA.</div><div id="controlSummary"></div></div><div class="card table"><h3>Empresas</h3><div id="controlTenants"></div></div><div class="card table"><h3>Usuarios y roles</h3><div id="controlUsers"></div><div id="cpUserCreate" data-cp-permission="user:create" class="settings" style="margin-top:12px"><label>ID usuario<input id="cpUserId" autocomplete="off"></label><label>Usuario<input id="cpUsername" autocomplete="off"></label><label>Nombre<input id="cpDisplayName" autocomplete="off"></label><label>Roles<input id="cpRoles" value="VIEWER" placeholder="VIEWER o ANALYST"></label><label>Contrasena<input id="cpUserPassword" type="password" autocomplete="new-password"></label></div><button id="cpCreateUserBtn" class="btn" data-cp-permission="user:create" onclick="controlCreateUser()">Crear usuario</button></div><div class="card table"><h3>Fuentes SQL Server</h3><div id="controlSql"></div><div id="cpSqlCreate" data-cp-permission="sql:configure" class="settings" style="margin-top:12px"><label>ID conexion<input id="cpSqlId" autocomplete="off"></label><label>Nombre<input id="cpSqlDisplay" autocomplete="off"></label><label>Servidor<input id="cpSqlServer" autocomplete="off"></label><label>Base de datos<input id="cpSqlDatabase" autocomplete="off"></label><label>Autenticacion<select id="cpSqlAuth"><option value="WINDOWS_INTEGRATED">Windows Integrated</option><option value="SQL_AUTH">SQL Auth</option></select></label><label>Usuario SQL<input id="cpSqlUsername" autocomplete="off"></label><label>Secret SQL<input id="cpSqlSecret" type="password" autocomplete="new-password"></label><label>Schemas permitidos<input id="cpSqlSchemas" value="dbo" placeholder="dbo"></label><label>Objetos permitidos<input id="cpSqlTables" placeholder="dbo.Tabla"></label><label>Max filas<input id="cpSqlMaxRows" type="number" min="1" max="5000" value="500"></label></div><button id="cpCreateSqlBtn" class="btn" data-cp-permission="sql:configure" onclick="controlCreateSql()">Crear conexion SQL</button></div><div class="card"><h3>Proveedor IA</h3><div id="controlAi"></div><div id="cpAiEditor" data-cp-permission="config:read" class="settings" style="margin-top:12px"><label>Tipo proveedor<select id="cpAiType"><option value="DISABLED">Desactivado</option><option value="OLLAMA">Ollama</option><option value="OPENAI_COMPATIBLE_LOCAL">OpenAI compatible local</option></select></label><label>URL local<input id="cpAiUrl" autocomplete="off" placeholder="http://localhost:11434"></label><label>Modelo<input id="cpAiModel" autocomplete="off"></label><label>Timeout<input id="cpAiTimeout" type="number" min="1" max="120" value="30"></label><label>Context window<input id="cpAiContext" type="number" min="1"></label><label>Habilitado<select id="cpAiEnabled"><option value="true">Si</option><option value="false">No</option></select></label></div><button class="btn" data-cp-permission="config:read" onclick="controlTestAi()">Probar proveedor</button> <button class="btn ok" data-cp-permission="config:write" onclick="controlSaveAi()">Guardar proveedor</button></div></section>
<section id="memoria" class="panel"><div class="card"><h3>Memoria permanente</h3><div class="formgrid"><input id="memText" placeholder="Conocimiento o preferencia"><select id="memCategory"><option>conocimiento_empresa</option><option>regla_negocio</option><option>definicion</option><option>preferencia</option><option>procedimiento</option></select></div><div style="margin-top:8px"><button class="btn" onclick="createMemory()">Guardar memoria</button></div></div><div class="card table" id="memoryTable"></div></section>
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
    })
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
            '/api/enterprise/control-plane/tenants',
            {headers:H()}
        );
        const tenants=data.tenants||[];
        const selected=controlTenantId();

        let selector='';

        if(controlSystemAdmin()){
            selector=
                '<label class="small">Empresa activa para administrar '+
                '<select id="cpTenantSelect" onchange="controlTenantChanged()">'+
                tenants.map(t=>
                    '<option value="'+esc(t.tenant_id)+'">'+
                    esc(t.name||t.tenant_id)+
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
                tenants,
                [
                    ['Tenant','tenant_id'],
                    ['Nombre','name'],
                    ['Estado','status',(v)=>pill(v)]
                ]
            );

        const select=controlElement('cpTenantSelect');
        if(select){
            const exists=[...select.options]
                .some(x=>x.value===selected);
            if(exists)select.value=selected
        }
    }catch(e){
        controlUnavailable('controlTenants',e.message)
    }
}

async function controlTenantChanged(){
    await Promise.allSettled([
        controlLoadOverview(),
        controlLoadUsers(),
        controlLoadSql(),
        controlLoadAi()
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

function controlSqlActions(profile){
    const actions=[];

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

        const action=profile.enabled?'disable':'enable';
        const label=profile.enabled?'Deshabilitar':'Habilitar';

        actions.push(
            '<button class="btn" onclick="controlSqlRun(\''+
            esc(profile.connection_id)+
            '\',\''+action+'\')">'+label+'</button>'
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

async function controlLoadSql(){
    if(!can('sql:read')){
        controlUnavailable('controlSql','SQL no autorizado.');
        return
    }

    try{
        const data=await api(
            '/api/admin/sql/connections'+controlTenantQuery(),
            {headers:H()}
        );

        CONTROL_SQL=data.items||[];

        controlElement('controlSql').innerHTML=
            table(
                CONTROL_SQL,
                [
                    ['Conexion','connection_id'],
                    ['Servidor','server'],
                    ['Base','database'],
                    ['Estado','status',(v)=>pill(v)],
                    ['Max filas','max_rows'],
                    ['Secret','secret_configured',(v)=>v?'Configurado':'N/A']
                ],
                controlSqlActions
            )
    }catch(e){
        controlUnavailable('controlSql',e.message)
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

        await controlLoadSql()
    }catch(e){
        toast(e.message,true)
    }
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

    try{
        const provider=controlAiFromForm();

        const result=await api(
            '/api/admin/ai/provider/test',
            {
                method:'POST',
                headers:{...H(),'Content-Type':'application/json'},
                body:JSON.stringify({provider})
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

        await api(
            '/api/admin/tenants/'+
            encodeURIComponent(tenant)+
            '/config',
            {
                method:'PATCH',
                headers:{...H(),'Content-Type':'application/json'},
                body:JSON.stringify({ai_provider:provider})
            }
        );

        toast('Proveedor IA guardado.');
        await controlLoadAi()
    }catch(e){
        toast(e.message,true)
    }
}

async function loadControlPlane(){
    const jobs=[];

    if(can('config:read')){
        jobs.push(controlLoadOverview());
        jobs.push(controlLoadAi())
    }else{
        controlUnavailable(
            'controlSummary',
            'Resumen no autorizado.'
        );
        controlUnavailable(
            'controlAi',
            'Configuracion IA no autorizada.'
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
document.querySelectorAll('#nav button').forEach(b=>b.onclick=()=>{document.querySelectorAll('#nav button').forEach(x=>x.classList.remove('active'));document.querySelectorAll('.panel').forEach(x=>x.classList.remove('active'));b.classList.add('active');document.getElementById(b.dataset.p).classList.add('active');if(b.dataset.p==='controlplane')loadControlPlane()});if(token){establishSession().then(ok=>{if(ok)refreshAll()})}else showLogin();
</script></body></html>'''
