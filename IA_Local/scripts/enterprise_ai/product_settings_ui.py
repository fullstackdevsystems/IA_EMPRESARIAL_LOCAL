from .product_workspaces_ui import page


SETTINGS_BODY = """
<style>
.settings-button{width:100%;border:0;text-align:left;background:transparent;color:inherit;border-radius:12px;padding:12px 14px;min-height:52px;cursor:pointer;font:inherit}.settings-button:hover{background:var(--surface-soft,#f4f7fb)}.settings-button.active-item{background:rgba(29,103,210,.10);outline:1px solid rgba(29,103,210,.18)}.settings-button .item-title{font-weight:800}.settings-button .item-meta{margin-top:3px}.hidden-panel{display:none!important}.users-head{display:flex;align-items:flex-start;justify-content:space-between;gap:16px;flex-wrap:wrap}.users-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;margin-top:16px}.user-card{border:1px solid var(--line,#dbe3ee);border-radius:14px;padding:14px;background:var(--surface,#fff)}.user-top{display:flex;justify-content:space-between;align-items:flex-start;gap:10px}.user-name{font-weight:800;font-size:15px}.user-login{font-size:13px;opacity:.72;margin-top:3px}.user-fields{display:grid;grid-template-columns:1fr 170px;gap:10px;margin-top:12px}.user-actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px}.user-actions .btn,.settings-button,#addUserButton,#cancelCreate,#createUser{min-height:44px}.status-pill{display:inline-flex;align-items:center;border-radius:999px;padding:5px 9px;font-size:12px;font-weight:800;background:rgba(34,197,94,.12)}.status-pill.off{background:rgba(148,163,184,.18)}.create-card{margin-top:16px;padding:16px;border:1px solid var(--line,var(--border,#dbe3ee));border-radius:14px;background:var(--surface-soft,var(--surface,#f8fafc))}#restoreArchive{min-height:44px;height:44px}#recoveryPanel .create-card>label.item-meta{min-height:44px;display:flex;align-items:center;gap:8px;cursor:pointer}#restoreConfirm{width:20px;height:20px;min-width:20px;min-height:20px;flex:0 0 20px;margin:0}.create-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.create-grid .full{grid-column:1/-1}.settings-future{opacity:.62}.settings-future .item-meta{margin-top:3px}@media(max-width:760px){.users-grid,.create-grid,.user-fields{grid-template-columns:1fr}.settings-button{min-height:56px}.user-actions .btn{flex:1 1 140px}.users-head .btn{width:100%}}
@media(max-width:820px){.main{height:calc(100dvh - 74px);overflow-y:auto;overscroll-behavior-y:contain}.content{padding-bottom:24px}}

.first-run-data-guide{margin:0 0 18px;padding:18px;border:1px solid var(--line,#dbe3ee);border-radius:16px;background:var(--surface-soft,#f8fafc)}
.first-run-kicker{font-size:13px;font-weight:800;color:var(--accent,#2563eb);margin-bottom:7px}
.first-run-progress{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;margin:14px 0 10px}
.first-run-step{min-height:44px;border:1px solid var(--line,#dbe3ee);border-radius:11px;padding:8px 9px;display:flex;align-items:center;gap:7px;font-size:12px;font-weight:700}
.first-run-step strong{display:grid;place-items:center;width:24px;height:24px;min-width:24px;border-radius:999px;background:rgba(148,163,184,.18)}
.first-run-step.done{opacity:.78}
.first-run-step.active{border-color:var(--accent,#2563eb);color:var(--accent,#2563eb);background:rgba(37,99,235,.06)}
.first-run-step.active strong{background:var(--accent,#2563eb);color:white}
.source-picker{margin-top:8px;border:1px solid var(--line,#dbe3ee);border-radius:12px;max-height:280px;overflow:auto;background:var(--surface,#fff)}
.source-picker-empty{padding:14px;color:var(--muted,#64748b);font-size:13px}
.source-option{display:flex;align-items:center;gap:10px;min-height:46px;padding:9px 12px;border-bottom:1px solid var(--line,#e2e8f0);cursor:pointer}
.source-option:last-child{border-bottom:0}
.source-option input{width:18px;height:18px;flex:0 0 auto}
.source-option span{overflow-wrap:anywhere}
.source-toolbar{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-top:9px}
.source-toolbar .btn{min-height:44px}
.setup-next-note{font-size:12px;color:var(--muted,#64748b);margin-top:8px}
html.first-run-setup .settings-grid{grid-template-columns:minmax(0,1fr)!important}
html.first-run-setup .company-menu{display:none!important}
html.first-run-setup #dataPanel,html.first-run-setup #aiPanel,html.first-run-setup #readyPanel{grid-column:1/-1!important;width:100%;max-width:1040px;margin-left:auto;margin-right:auto}
html[data-theme="professional-dark"] .first-run-data-guide{background:#182438;border-color:#33435b;color:#f8fafc}
html[data-theme="professional-dark"] .first-run-data-guide h2{color:#f8fafc}
html[data-theme="professional-dark"] .first-run-data-guide .copy{color:#cbd5e1}
html[data-theme="professional-dark"] .first-run-data-guide .setup-next-note{color:#cbd5e1}
html[data-theme="professional-dark"] .first-run-step{background:#111c2f;border-color:#3a4a63;color:#dbe5f2;opacity:1}
html[data-theme="professional-dark"] .first-run-step.done{color:#b9c7d8;opacity:.88}
html[data-theme="professional-dark"] .first-run-step.active{background:rgba(48,92,219,.18);border-color:#5b83ff;color:#ffffff}
@media(max-width:760px){
  html.first-run-setup #dataPanel,html.first-run-setup #aiPanel,html.first-run-setup #readyPanel{max-width:none;margin:0}
  html.first-run-setup .settings-grid{display:block!important}
  html.first-run-setup .first-run-data-guide{margin-top:0}
}
@media(max-width:760px){
  .first-run-progress{grid-template-columns:repeat(2,minmax(0,1fr))}
  .source-toolbar{align-items:stretch;flex-direction:column}
  .source-toolbar .btn{width:100%}
}

</style>
<div class="grid settings-grid">
<aside class="card s5 company-menu">
<h2>Configuración</h2>
<p class="copy">Administra cómo funciona IA Empresarial Local en tu empresa.</p>
<div class="list settings-list">
<button id="companyTab" class="settings-button active-item" type="button"><div class="item-title">Mi empresa</div><div class="item-meta">Información general e identidad de tu organización.</div></button>
<button id="usersTab" class="settings-button" type="button"><div class="item-title">Usuarios</div><div class="item-meta">Personas, accesos y responsabilidades.</div></button>
<button id="dataTab" class="settings-button" type="button"><div class="item-title">Datos y conexiones</div><div class="item-meta">Información que tu empresa autoriza para analizar.</div></button>
<button id="aiTab" class="settings-button" type="button"><div class="item-title">Inteligencia artificial</div><div class="item-meta">Motor local y modelo para el asistente.</div></button>
<button id="appearanceTab" class="settings-button" type="button"><div class="item-title">Apariencia</div><div class="item-meta">Tema y color que distinguen este espacio.</div></button>
<button id="recoveryTab" class="settings-button" type="button"><div class="item-title">Seguridad y recuperación</div><div class="item-meta">Respalda y recupera la información protegida.</div></button>
<button id="advancedTab" class="settings-button" type="button"><div class="item-title">Avanzado</div><div class="item-meta">Preferencias regionales de este espacio.</div></button>
</div>
</aside>
<section id="companyPanel" class="card s7">
<div class="section-head"><div><h2>Mi empresa</h2><p class="copy">Mantén actualizada la identidad con la que tu equipo reconoce este espacio de trabajo.</p></div></div>
<div id="companyStatus" class="status info hidden"></div>
<div class="field"><label for="companyName">Nombre de la empresa</label><input id="companyName" type="text" maxlength="120" autocomplete="organization"></div>
<div class="field"><label for="businessType">Tipo de empresa</label><select id="businessType"><option>Comercial</option><option>Distribución</option><option>Servicios</option><option>Manufactura</option><option>Logística</option><option>Agropecuario</option><option>Otro</option></select></div>
<div class="field"><label for="accentColor">Color principal</label><div class="color-row"><input id="accentColor" type="color" value="#1d67d2"><span id="accentText" class="item-meta"></span></div></div>
<div class="field"><label for="companyTheme">Tema visual</label><select id="companyTheme"><option value="professional-light">Claro</option><option value="professional-dark">Oscuro</option></select></div>
<div class="field"><label>Logotipo</label><div id="logoStatus" class="logo-status">Sin logotipo configurado.</div><p class="item-meta">La carga de logotipos se habilitará cuando exista una gestión segura de archivos de identidad.</p></div>
<div class="actions"><button id="saveCompany" class="btn primary">Guardar cambios</button></div>
</section>
<section id="usersPanel" class="card s7 hidden-panel">
<div class="users-head"><div><h2>Usuarios</h2><p class="copy">Administra quién puede entrar y qué responsabilidad tiene cada persona.</p></div><button id="addUserButton" class="btn primary" type="button" disabled>Agregar usuario</button></div>
<div id="usersStatus" class="status info hidden"></div>
<div id="createUserPanel" class="create-card hidden-panel">
<h3>Agregar usuario</h3>
<div class="create-grid">
<div class="field"><label for="newDisplayName">Nombre</label><input id="newDisplayName" type="text" maxlength="120" autocomplete="name"></div>
<div class="field"><label for="newUsername">Usuario</label><input id="newUsername" type="text" maxlength="80" autocomplete="username"></div>
<div class="field"><label for="newRole">Rol</label><select id="newRole"><option value="administrator">Administrador</option><option value="analyst">Analista</option><option value="viewer">Consulta</option></select></div>
<div></div>
<div class="field"><label for="newPassword">Contraseña temporal</label><input id="newPassword" type="password" minlength="12" maxlength="256" autocomplete="new-password"></div>
<div class="field"><label for="confirmPassword">Confirmar contraseña</label><input id="confirmPassword" type="password" minlength="12" maxlength="256" autocomplete="new-password"></div>
<div class="actions full"><button id="createUser" class="btn primary" type="button">Crear usuario</button><button id="cancelCreate" class="btn" type="button">Cancelar</button></div>
</div>
</div>
<div id="usersList" class="users-grid"></div>
</section>
<section id="dataPanel" class="card s7 hidden-panel">
<div id="firstRunDataGuide" class="first-run-data-guide hidden-panel">
<div class="first-run-kicker">Primera configuración · Paso 2 de 4</div>
<h2 style="margin:0">Conecta tus datos</h2>
<p class="copy">Indica dónde está la información de tu empresa. Primero comprobaremos el acceso y después podrás elegir exactamente qué tablas autorizar.</p>
<div class="first-run-progress" aria-label="Progreso de configuración">
<div class="first-run-step done"><strong>1</strong><span>Empresa</span></div>
<div class="first-run-step active" aria-current="step"><strong>2</strong><span>Datos</span></div>
<div class="first-run-step"><strong>3</strong><span>IA</span></div>
<div class="first-run-step"><strong>4</strong><span>Listo</span></div>
</div>
<div class="setup-next-note">La conexión será de solo lectura. Podrás modificarla después desde Configuración.</div>
</div>

<div class="users-head">
<div>
<h2>Datos y conexiones</h2>
<p class="copy">Conecta la información de tu empresa para analizarla de forma segura.</p>
</div>
<button id="addConnectionButton" class="btn primary" type="button" disabled>Agregar conexión</button>
</div>

<div id="dataStatus" class="status info hidden"></div>

<div id="createConnectionPanel" class="create-card hidden-panel">
<h3>Agregar conexión</h3>
<p class="item-meta">Primero verifica el acceso. IA Empresarial Local buscará las tablas disponibles sin guardar la contraseña durante esta comprobación.</p>

<div class="create-grid">
<div class="field">
<label for="connectionName">Nombre de la conexión</label>
<input id="connectionName" type="text" maxlength="120" placeholder="Ej. Sistema de ventas">
</div>

<div class="field">
<label for="connectionServer">Servidor de datos</label>
<input id="connectionServer" type="text" maxlength="255" placeholder="Ej. SERVIDOR\\INSTANCIA">
</div>

<div class="field">
<label for="connectionDatabase">Base de datos</label>
<input id="connectionDatabase" type="text" maxlength="255" placeholder="Ej. Ventas">
</div>

<div class="field">
<label for="connectionAccess">Cómo acceder</label>
<select id="connectionAccess">
<option value="windows">Usar acceso de Windows</option>
<option value="password">Usar usuario y contraseña</option>
</select>
<div class="field">
  <label for="connectionTrustCertificate" style="display:flex;align-items:flex-start;gap:10px">
    <input id="connectionTrustCertificate" type="checkbox" style="width:18px;height:18px;min-height:18px;margin-top:2px">
    <span>Mi servidor usa un certificado interno</span>
  </label>
  <div class="copy">Actívalo si el servidor pertenece a tu empresa pero su certificado no es reconocido por Windows.</div>
</div>
</div>

<div id="connectionCredentials" class="create-grid full hidden-panel">
<div class="field">
<label for="connectionUsername">Usuario</label>
<input id="connectionUsername" type="text" maxlength="160" autocomplete="username">
</div>
<div class="field">
<label for="connectionPassword">Contraseña</label>
<input id="connectionPassword" type="password" maxlength="256" autocomplete="new-password">
</div>
</div>

<div class="actions full">
<button id="probeConnection" class="btn" type="button">Probar conexión y buscar tablas</button>
</div>

<div id="connectionProbeStatus" class="status info hidden full"></div>

<div class="field full">
<label>Fuentes autorizadas</label>
<p class="item-meta">Selecciona únicamente la información que IA Empresarial Local podrá consultar.</p>
<div class="source-toolbar">
<span id="connectionSourceCount" class="item-meta">Primero prueba la conexión.</span>
<button id="selectAllSources" class="btn" type="button" disabled>Seleccionar todo</button>
</div>
<div id="connectionSourcePicker" class="source-picker">
<div class="source-picker-empty">Las tablas disponibles aparecerán aquí después de verificar la conexión.</div>
</div>
<input id="connectionSources" type="hidden">
</div>

<div class="actions full">
<button id="createConnection" class="btn primary" type="button" disabled>Guardar conexión y continuar</button>
<button id="cancelConnection" class="btn" type="button">Cancelar</button>
<button id="skipDataSetup" class="btn hidden-panel" type="button">Configurar después</button>
</div>
</div>
</div>

<div id="connectionsList" class="users-grid"></div>
</section>
<section id="aiPanel" class="card s7 hidden-panel">
<div class="users-head"><div><h2>Inteligencia artificial</h2><p class="copy">Elige cómo quieres que el asistente trabaje en este equipo.</p></div></div>
<div id="aiStatus" class="status info hidden"></div>
<div class="field"><label>Estado</label><div id="aiState" class="logo-status">Cargando configuración...</div></div>
<div class="field"><label for="aiEngine">Motor local</label><select id="aiEngine"><option value="disabled">Sin inteligencia artificial</option><option value="ollama">Ollama</option><option value="local-compatible">Motor local compatible</option></select></div>
<div class="field"><label for="aiModel">Modelo principal</label><select id="aiModel"><option value="">Selecciona un modelo</option></select><p class="item-meta">Selecciona el motor y detecta los modelos disponibles antes de guardar.</p></div>
<div class="actions"><button id="detectAi" class="btn" type="button">Detectar modelos</button><button id="testAi" class="btn" type="button">Probar configuración</button><button id="saveAi" class="btn primary" type="button">Guardar cambios</button><button id="continueAiSetup" class="btn primary hidden-panel" type="button">Continuar</button></div>
</section>
<section id="readyPanel" class="card s7 hidden-panel">
<div class="section-head"><div><h2>Preparación final</h2><p class="copy">Confirma que tu empresa esté lista antes de comenzar.</p></div></div>
<div id="readyStatus" class="status info hidden"></div>
<div class="users-grid">
<article class="user-card"><div class="user-top"><div><div class="user-name">Empresa</div><div class="user-login">Información principal de tu organización</div></div><span id="readyCompany" class="status-pill">Revisando...</span></div></article>
<article class="user-card"><div class="user-top"><div><div class="user-name">Administrador</div><div class="user-login">Acceso responsable del espacio de trabajo</div></div><span id="readyAdmin" class="status-pill">Revisando...</span></div></article>
<article class="user-card"><div class="user-top"><div><div class="user-name">Datos</div><div class="user-login">Conexión empresarial preparada</div></div><span id="readyData" class="status-pill">Revisando...</span></div></article>
<article class="user-card"><div class="user-top"><div><div class="user-name">Inteligencia artificial</div><div class="user-login">Asistente local configurado</div></div><span id="readyAi" class="status-pill">Revisando...</span></div></article>
</div>
<div class="field"><label>Estado general</label><div id="readyOverall" class="logo-status">Validando preparación...</div></div>
<div id="readyHint" class="item-meta">Estamos revisando la configuración.</div>
<div class="actions"><button id="refreshReady" class="btn" type="button">Actualizar preparación</button><button id="reviewSettings" class="btn" type="button">Revisar configuración</button><button id="enterProduct" class="btn primary" type="button" disabled>Entrar a IA Empresarial Local</button></div>
</section>
<section id="appearancePanel" class="card s7 hidden-panel">
<div class="section-head"><div><h2>Apariencia</h2><p class="copy">Personaliza la presentación visual para tu equipo.</p></div></div>
<div id="appearanceStatus" class="status info hidden"></div>
<div class="field"><label for="appearanceTheme">Tema</label><select id="appearanceTheme"><option value="professional-light">Claro</option><option value="professional-dark">Oscuro</option></select></div>
<div class="field"><label for="appearanceAccent">Color principal</label><div class="color-row"><input id="appearanceAccent" type="color" value="#1d67d2"><span id="appearanceAccentText" class="item-meta"></span></div></div>
<div class="actions"><button id="saveAppearance" class="btn primary" type="button">Guardar apariencia</button></div>
</section>
<section id="recoveryPanel" class="card s7 hidden-panel"><div class="section-head"><div><h2>Seguridad y recuperación</h2><p class="copy">Protege la información de tu empresa con respaldos controlados.</p></div></div><div id="recoveryStatus" class="status info hidden"></div><div id="recoveryState" class="logo-status">Cargando estado...</div><div class="actions"><button id="createBackup" class="btn primary" type="button">Crear respaldo</button></div><div class="create-card"><h3>Recuperar respaldo</h3><p class="item-meta">Esta acción reemplaza la información actual. Confirma antes de continuar.</p><div class="field"><label for="restoreArchive">Archivo de respaldo</label><input id="restoreArchive" type="file" accept=".zip"></div><label class="item-meta"><input id="restoreConfirm" type="checkbox"> Confirmo que deseo recuperar este respaldo.</label><div class="actions"><button id="restoreBackup" class="btn" type="button">Recuperar información</button></div></div></section>
<section id="advancedPanel" class="card s7 hidden-panel"><div class="section-head"><div><h2>Avanzado</h2><p class="copy">Ajusta las preferencias regionales que usa este espacio de trabajo.</p></div></div><div id="advancedStatus" class="status info hidden"></div><div class="field"><label for="advancedLocale">Idioma y formato</label><select id="advancedLocale"><option value="es-MX">Español (México)</option></select></div><div class="field"><label for="advancedTimezone">Zona horaria</label><select id="advancedTimezone"><option value="America/Chihuahua">Chihuahua</option><option value="America/Mexico_City">Ciudad de México</option></select></div><div class="actions"><button id="saveAdvanced" class="btn primary" type="button">Guardar preferencias</button></div></section>
</div>
"""

SETTINGS_JS = """
let USERS_CAPS={can_create:false,can_update:false,can_disable:false,can_assign_role:false};
function companyPayload(){return {display_name:q("companyName").value.trim(),business_type:q("businessType").value,accent_color:q("accentColor").value,theme:q("companyTheme").value}}
function companyForm(p){const c=(p||{}).company||{};q("companyName").value=txt(c.display_name||"");q("businessType").value=txt(c.business_type||"Otro");q("accentColor").value=txt(c.accent_color||"#1d67d2");q("companyTheme").value=txt(c.theme||"professional-light");q("accentText").textContent=q("accentColor").value.toUpperCase();q("logoStatus").textContent=c.logo_configured?"Logotipo configurado.":"Sin logotipo configurado.";q("saveCompany").disabled=!Boolean(p&&p.can_edit)}
async function loadCompany(){const r=await pf("/api/enterprise/company-profile");if(!r)return;const d=await r.json().catch(()=>({}));if(!r.ok){status("companyStatus","No se pudo cargar la información de la empresa.","error");return}companyForm(d);if(!d.can_edit)status("companyStatus","Puedes consultar esta información, pero no tienes permiso para modificarla.","info")}
async function saveCompany(){const b=q("saveCompany"),body=companyPayload();if(!body.display_name){status("companyStatus","Escribe el nombre de la empresa.","warning");return}b.disabled=true;status("companyStatus","Guardando cambios...","info");try{const r=await pf("/api/enterprise/company-profile",{method:"PUT",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});if(!r)return;const d=await r.json().catch(()=>({}));if(r.status===403){status("companyStatus","No tienes permiso para modificar la empresa.","error");return}if(!r.ok){status("companyStatus",typeof d.detail==="string"?d.detail:"No se pudieron guardar los cambios.","error");return}companyForm(d);if(APP){APP.company={...(APP.company||{}),...(d.company||{})};applyContext(APP)}status("companyStatus","Cambios guardados correctamente.","success")}catch(_){status("companyStatus","No se pudo conectar con el servicio local.","error")}finally{b.disabled=false}}
let DATA_CAPS={can_configure:false};
function showSettingsPanel(name){const company=name==="company",users=name==="users",data=name==="data",ai=name==="ai",ready=name==="ready",appearance=name==="appearance",recovery=name==="recovery",advanced=name==="advanced";q("companyPanel").classList.toggle("hidden-panel",!company);q("usersPanel").classList.toggle("hidden-panel",!users);q("dataPanel").classList.toggle("hidden-panel",!data);q("aiPanel").classList.toggle("hidden-panel",!ai);q("readyPanel").classList.toggle("hidden-panel",!ready);q("appearancePanel").classList.toggle("hidden-panel",!appearance);q("recoveryPanel").classList.toggle("hidden-panel",!recovery);q("advancedPanel").classList.toggle("hidden-panel",!advanced);q("companyTab").classList.toggle("active-item",company);q("usersTab").classList.toggle("active-item",users);q("dataTab").classList.toggle("active-item",data);q("aiTab").classList.toggle("active-item",ai);q("appearanceTab").classList.toggle("active-item",appearance);q("recoveryTab").classList.toggle("active-item",recovery);q("advancedTab").classList.toggle("active-item",advanced);if(users)loadUsers();if(data)loadConnections();if(ai)loadAiConfiguration();if(ready)loadReadySetup();if(appearance)loadAppearance();if(recovery)loadRecovery();if(advanced)loadAdvanced()}
function aiMessage(message,kind){status("aiStatus",message,kind||"info")}
let AI_VERIFIED_FINGERPRINT="";
function aiSetupMode(){return new URLSearchParams(window.location.search).get("setup")==="ai"}
function aiFingerprint(){return q("aiEngine").value+"|"+q("aiModel").value.trim()}
function invalidateAiVerification(){AI_VERIFIED_FINGERPRINT=""}
function renderAiConfiguration(payload){const c=(payload&&payload.configuration)||{};q("aiEngine").value=String(c.engine||"disabled");const select=q("aiModel"),model=String(c.model||"");if(![...select.options].some(o=>o.value===model)&&model){const option=document.createElement("option");option.value=model;option.textContent=model;select.appendChild(option)}select.value=model;q("aiState").textContent=String(c.status_label||"Requiere configuración");const editable=Boolean(c.can_edit);q("aiEngine").disabled=!editable;q("aiModel").disabled=!editable;q("saveAi").disabled=!editable;q("detectAi").disabled=!editable;q("testAi").disabled=false}
async function loadAiConfiguration(){aiMessage("Cargando configuración...","info");try{const r=await pf("/api/enterprise/ai-configuration");if(!r)return;const d=await r.json().catch(()=>({}));if(r.status===403){aiMessage("No tienes permiso para consultar esta configuración.","info");return}if(!r.ok){aiMessage("No se pudo cargar la configuración.","error");return}renderAiConfiguration(d);aiMessage("Configuración actualizada.","success")}catch(_){aiMessage("No se pudo conectar con el servicio local.","error")}}
async function saveAiConfiguration(){const button=q("saveAi"),engine=q("aiEngine").value,model=q("aiModel").value.trim();if(engine!=="disabled"&&!model){aiMessage("Selecciona un modelo para continuar.","warning");return}if(aiSetupMode()&&engine!=="disabled"&&AI_VERIFIED_FINGERPRINT!==aiFingerprint()){aiMessage("Prueba la configuración actual antes de guardar.","warning");return}button.disabled=true;aiMessage("Guardando cambios...","info");try{const r=await pf("/api/enterprise/ai-configuration",{method:"PUT",headers:{"Content-Type":"application/json"},body:JSON.stringify({engine:engine,model:model||null})});if(!r)return;const d=await r.json().catch(()=>({}));if(!r.ok){aiMessage(userError(d,"No se pudieron guardar los cambios."),"error");return}renderAiConfiguration(d);aiMessage("Configuración guardada correctamente.","success")}catch(_){aiMessage("No se pudo conectar con el servicio local.","error")}finally{button.disabled=false}}
async function detectAiModels(){invalidateAiVerification();const button=q("detectAi"),engine=q("aiEngine").value;button.disabled=true;aiMessage("Buscando modelos disponibles...","info");try{const r=await pf("/api/enterprise/ai-configuration/detect",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({engine:engine,model:null})});if(!r)return;const d=await r.json().catch(()=>({}));const select=q("aiModel"),current=select.value;select.replaceChildren();const empty=document.createElement("option");empty.value="";empty.textContent="Selecciona un modelo";select.appendChild(empty);for(const item of (d.models||[])){const option=document.createElement("option");option.value=String(item.id||"");option.textContent=String(item.name||item.id||"");select.appendChild(option)}if([...select.options].some(o=>o.value===current))select.value=current;aiMessage(d.status_label||"No se pudieron detectar modelos.",r.ok?"success":"error")}catch(_){aiMessage("No se pudo conectar con el servicio local.","error")}finally{button.disabled=false}}
async function testAiConfiguration(){const button=q("testAi"),engine=q("aiEngine").value,model=q("aiModel").value.trim();if(engine!=="disabled"&&!model){invalidateAiVerification();aiMessage("Selecciona un modelo para probar la configuración.","warning");return}button.disabled=true;aiMessage("Verificando configuración...","info");try{const r=await pf("/api/enterprise/ai-configuration/test",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({engine:engine,model:model||null})});if(!r){invalidateAiVerification();return}const d=await r.json().catch(()=>({}));const verified=Boolean(r.ok&&d.ok);AI_VERIFIED_FINGERPRINT=verified?aiFingerprint():"";aiMessage(verified?"Configuración verificada.":(d.message||"No se pudo verificar la configuración."),verified?"success":"warning")}catch(_){invalidateAiVerification();aiMessage("No se pudo conectar con el servicio local.","error")}finally{button.disabled=false}}
function friendlyReadyState(value){const state=String(value||"").toUpperCase();return {READY:"Listo",TESTED:"Verificado",PASS:"Verificado",CONFIGURED:"Configurado",ACTIVE:"Listo",BLOCKED:"Requiere configuración",DEGRADED:"Requiere atención",UNAVAILABLE:"Requiere atención",NOT_CONFIGURED:"Requiere configuración"}[state]||"Revisar"}
function setReadyStep(id,step){const target=q(id),state=String((step||{}).status||"BLOCKED").toUpperCase();target.textContent=friendlyReadyState(state);target.classList.toggle("off",["BLOCKED","DEGRADED","UNAVAILABLE","NOT_CONFIGURED"].includes(state))}
function renderReadySetup(payload){const readiness=(payload&&payload.readiness)||{},steps=readiness.steps||{},overall=String(readiness.status||"BLOCKED").toUpperCase();setReadyStep("readyCompany",steps.company);setReadyStep("readyAdmin",steps.admin);setReadyStep("readyData",steps.sql);setReadyStep("readyAi",steps.ai);q("readyOverall").textContent=friendlyReadyState(overall);const ready=overall==="READY";q("enterProduct").disabled=!ready;q("readyHint").textContent=ready?"Todo está listo. Puedes entrar a tu espacio de trabajo.":"Hay elementos pendientes. Revisa la configuración y vuelve a validar.";status("readyStatus",ready?"Tu empresa está lista para comenzar.":"La preparación todavía requiere atención.",ready?"success":"warning")}
async function loadReadySetup(){status("readyStatus","Validando preparación...","info");q("refreshReady").disabled=true;q("enterProduct").disabled=true;try{const r=await pf("/api/enterprise/readiness/validate",{method:"POST"});if(!r)return;const d=await r.json().catch(()=>({}));if(!r.ok){status("readyStatus","No se pudo validar la preparación.","error");return}renderReadySetup(d)}catch(_){status("readyStatus","No se pudo conectar con el servicio local.","error")}finally{q("refreshReady").disabled=false}}
async function continueAiSetup(){try{const r=await pf("/api/enterprise/ai-configuration");if(!r)return;const d=await r.json().catch(()=>({}));if(!r.ok){aiMessage("No se pudo comprobar la configuración guardada.","error");return}const c=d.configuration||{},state=String(c.state||"BLOCKED").toUpperCase();if(state==="BLOCKED"){aiMessage("Completa la configuración de inteligencia artificial antes de continuar.","warning");return}window.location.assign("/settings?setup=ready")}catch(_){aiMessage("No se pudo conectar con el servicio local.","error")}}
function renderAppearance(payload){const a=(payload&&payload.appearance)||{};q("appearanceTheme").value=String(a.theme||"professional-light");q("appearanceAccent").value=String(a.accent_color||"#1d67d2");q("appearanceAccentText").textContent=q("appearanceAccent").value.toUpperCase();q("saveAppearance").disabled=!Boolean(a.can_edit)}
async function loadAppearance(){status("appearanceStatus","Cargando apariencia...","info");try{const r=await pf("/api/enterprise/appearance");if(!r)return;const d=await r.json().catch(()=>({}));if(r.status===403){status("appearanceStatus","No tienes permiso para consultar esta configuración.","info");return}if(!r.ok){status("appearanceStatus","No se pudo cargar la apariencia.","error");return}renderAppearance(d);status("appearanceStatus","Apariencia actualizada.","success")}catch(_){status("appearanceStatus","No se pudo conectar con el servicio local.","error")}}
async function saveAppearance(){const button=q("saveAppearance"),body={theme:q("appearanceTheme").value,accent_color:q("appearanceAccent").value};button.disabled=true;status("appearanceStatus","Guardando cambios...","info");try{const r=await pf("/api/enterprise/appearance",{method:"PUT",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});if(!r)return;const d=await r.json().catch(()=>({}));if(!r.ok){status("appearanceStatus",userError(d,"No se pudo guardar la apariencia."),"error");return}renderAppearance(d);if(APP){APP.company={...(APP.company||{}),theme:body.theme,accent_color:body.accent_color};applyContext(APP)}status("appearanceStatus","Apariencia guardada correctamente.","success")}catch(_){status("appearanceStatus","No se pudo conectar con el servicio local.","error")}finally{button.disabled=false}}
async function loadRecovery(){const r=await pf("/api/enterprise/security-recovery");if(!r)return;const d=await r.json().catch(()=>({}));if(!r.ok){status("recoveryStatus","No se pudo cargar el estado de protección.","error");return}q("recoveryState").textContent=String(d.protection||"Configurada");q("createBackup").disabled=!d.backup_available;q("restoreBackup").disabled=!d.recovery_available}
async function createBackup(){const r=await pf("/api/enterprise/security-recovery/backup",{method:"POST"});if(!r){return}if(!r.ok){status("recoveryStatus","No se pudo crear el respaldo.","error");return}const link=document.createElement("a");link.href=URL.createObjectURL(await r.blob());link.download="IA-Empresarial-Local-respaldo.zip";link.click();URL.revokeObjectURL(link.href);status("recoveryStatus","Respaldo preparado correctamente.","success")}
async function restoreBackup(){const archive=q("restoreArchive").files[0];if(!archive||!q("restoreConfirm").checked){status("recoveryStatus","Selecciona un respaldo y confirma la recuperación.","warning");return}const form=new FormData();form.append("archive",archive);const r=await pf("/api/enterprise/security-recovery/restore?confirmed=true",{method:"POST",body:form});q("restoreArchive").value="";q("restoreConfirm").checked=false;if(!r)return;const d=await r.json().catch(()=>({}));status("recoveryStatus",r.ok?"Información recuperada correctamente.":userError(d,"No se pudo recuperar el respaldo."),r.ok?"success":"error")}
async function loadAdvanced(){const r=await pf("/api/enterprise/advanced-preferences");if(!r)return;const d=await r.json().catch(()=>({}));if(!r.ok){status("advancedStatus","No se pudieron cargar las preferencias.","error");return}const p=d.preferences||{};q("advancedLocale").value=String(p.locale||"es-MX");q("advancedTimezone").value=String(p.timezone||"America/Chihuahua");q("saveAdvanced").disabled=!p.can_edit}
async function saveAdvanced(){const r=await pf("/api/enterprise/advanced-preferences",{method:"PUT",headers:{"Content-Type":"application/json"},body:JSON.stringify({locale:q("advancedLocale").value,timezone:q("advancedTimezone").value})});if(!r)return;const d=await r.json().catch(()=>({}));status("advancedStatus",r.ok?"Preferencias guardadas correctamente.":userError(d,"No se pudieron guardar las preferencias."),r.ok?"success":"error")}
function showCreateUser(show){q("createUserPanel").classList.toggle("hidden-panel",!show);if(show){q("newDisplayName").focus()}else{q("newDisplayName").value="";q("newUsername").value="";q("newRole").value="viewer";q("newPassword").value="";q("confirmPassword").value=""}}
function userError(d,fallback){const detail=d&&d.detail;if(typeof detail==="string"&&detail)return detail;if(detail&&typeof detail==="object")return String(detail.message||detail.code||fallback);return fallback}
function makeElement(tag,className,text){const el=document.createElement(tag);if(className)el.className=className;if(text!==undefined)el.textContent=String(text);return el}
function renderUsers(payload){USERS_CAPS=(payload&&payload.capabilities)||USERS_CAPS;q("addUserButton").disabled=!USERS_CAPS.can_create;const host=q("usersList");host.replaceChildren();const users=Array.isArray(payload&&payload.users)?payload.users:[];if(!users.length){host.appendChild(makeElement("div","item-meta","Aún no hay usuarios para mostrar."));return}for(const user of users){const card=makeElement("article","user-card");const top=makeElement("div","user-top");const who=makeElement("div");who.appendChild(makeElement("div","user-name",user.display_name||user.username));who.appendChild(makeElement("div","user-login","Usuario: "+String(user.username||"")));const pill=makeElement("span","status-pill"+(user.enabled?"":" off"),user.status_label|| (user.enabled?"Activo":"Desactivado"));top.append(who,pill);card.appendChild(top);const fields=makeElement("div","user-fields");const nameWrap=makeElement("div","field");const nameLabel=makeElement("label","","Nombre");const nameInput=document.createElement("input");nameInput.type="text";nameInput.maxLength=120;nameInput.value=String(user.display_name||"");nameInput.disabled=!USERS_CAPS.can_update;nameWrap.append(nameLabel,nameInput);const roleWrap=makeElement("div","field");const roleLabel=makeElement("label","","Rol");const roleSelect=document.createElement("select");for(const item of [["administrator","Administrador"],["analyst","Analista"],["viewer","Consulta"]]){const option=document.createElement("option");option.value=item[0];option.textContent=item[1];roleSelect.appendChild(option)}if(user.role==="custom"){const custom=document.createElement("option");custom.value="custom";custom.textContent="Acceso personalizado";roleSelect.appendChild(custom)}roleSelect.value=String(user.role||"viewer");roleSelect.disabled=!(USERS_CAPS.can_assign_role&&user.role_editable);roleWrap.append(roleLabel,roleSelect);fields.append(nameWrap,roleWrap);card.appendChild(fields);const actions=makeElement("div","user-actions");const save=makeElement("button","btn","Guardar");save.type="button";save.disabled=!USERS_CAPS.can_update;save.onclick=()=>saveUser(user,nameInput,roleSelect,save);const toggle=makeElement("button","btn",user.enabled?"Desactivar":"Activar");toggle.type="button";toggle.disabled=!(USERS_CAPS.can_disable&&user.status_editable);toggle.onclick=()=>toggleUser(user,toggle);actions.append(save,toggle);if(user.is_current)actions.appendChild(makeElement("span","item-meta","Tu acceso actual"));card.appendChild(actions);host.appendChild(card)}}
async function loadUsers(){status("usersStatus","Cargando usuarios...","info");try{const r=await pf("/api/enterprise/users");if(!r)return;const d=await r.json().catch(()=>({}));if(r.status===403){USERS_CAPS={can_create:false,can_update:false,can_disable:false,can_assign_role:false};q("addUserButton").disabled=true;q("usersList").replaceChildren();status("usersStatus","No tienes permiso para administrar usuarios.","info");return}if(!r.ok){status("usersStatus",userError(d,"No se pudieron cargar los usuarios."),"error");return}renderUsers(d);status("usersStatus","Usuarios actualizados.","success")}catch(_){status("usersStatus","No se pudo conectar con el servicio local.","error")}}
async function createUser(){const button=q("createUser"),password=q("newPassword").value,confirm=q("confirmPassword").value,body={display_name:q("newDisplayName").value.trim(),username:q("newUsername").value.trim(),role:q("newRole").value,password:password};if(!body.display_name||!body.username){status("usersStatus","Completa el nombre y el usuario.","warning");return}if(password.length<12){status("usersStatus","La contraseña temporal debe tener al menos 12 caracteres.","warning");return}if(password!==confirm){status("usersStatus","Las contraseñas no coinciden.","warning");return}button.disabled=true;try{const r=await pf("/api/enterprise/users",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});if(!r)return;const d=await r.json().catch(()=>({}));if(!r.ok){status("usersStatus",userError(d,"No se pudo crear el usuario."),"error");return}showCreateUser(false);status("usersStatus","Usuario creado correctamente.","success");await loadUsers()}catch(_){status("usersStatus","No se pudo conectar con el servicio local.","error")}finally{q("newPassword").value="";q("confirmPassword").value="";button.disabled=false}}
async function saveUser(user,nameInput,roleSelect,button){const body={display_name:nameInput.value.trim()};if(!body.display_name){status("usersStatus","El nombre no puede quedar vacío.","warning");return}if(!roleSelect.disabled&&roleSelect.value!=="custom")body.role=roleSelect.value;button.disabled=true;try{const r=await pf("/api/enterprise/users/"+encodeURIComponent(user.username),{method:"PATCH",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});if(!r)return;const d=await r.json().catch(()=>({}));if(!r.ok){status("usersStatus",userError(d,"No se pudieron guardar los cambios."),"error");return}status("usersStatus","Cambios del usuario guardados.","success");await loadUsers()}catch(_){status("usersStatus","No se pudo conectar con el servicio local.","error")}finally{button.disabled=false}}
async function toggleUser(user,button){const enabled=!Boolean(user.enabled);button.disabled=true;try{const r=await pf("/api/enterprise/users/"+encodeURIComponent(user.username)+"/status",{method:"PUT",headers:{"Content-Type":"application/json"},body:JSON.stringify({enabled:enabled})});if(!r)return;const d=await r.json().catch(()=>({}));if(!r.ok){status("usersStatus",userError(d,"No se pudo cambiar el acceso del usuario."),"error");return}status("usersStatus",enabled?"Usuario activado.":"Usuario desactivado.","success");await loadUsers()}catch(_){status("usersStatus","No se pudo conectar con el servicio local.","error")}finally{button.disabled=false}}
let DATA_PROBE_VALID=false;
let DATA_PROBE_OBJECTS=[];

function dataSetupMode(){
  return new URLSearchParams(window.location.search).get("setup")==="data";
}

function dataProbeError(payload,fallback){
  const detail=payload&&payload.detail;
  if(typeof detail==="string"&&detail)return detail;
  if(detail&&typeof detail==="object"){
    return String(detail.message||detail.code||fallback);
  }
  return fallback;
}

function selectedProbeSources(){
  return Array.from(
    q("connectionSourcePicker").querySelectorAll(
      'input[type="checkbox"]:checked'
    )
  ).map(item=>String(item.value||"").trim()).filter(Boolean);
}

function syncProbeSelection(){
  const selected=selectedProbeSources();
  q("connectionSources").value=selected.join(",");
  q("connectionSourceCount").textContent=
    selected.length
      ? String(selected.length)+" fuente"+(selected.length===1?"":"s")+" seleccionada"+(selected.length===1?"":"s")
      : (DATA_PROBE_OBJECTS.length
          ? "Selecciona al menos una fuente."
          : "Primero prueba la conexión.");
  q("createConnection").disabled=
    !(DATA_PROBE_VALID&&selected.length&&DATA_CAPS.can_configure);
}

function renderProbeSources(objects){
  DATA_PROBE_OBJECTS=Array.isArray(objects)?objects:[];
  const host=q("connectionSourcePicker");
  host.replaceChildren();

  if(!DATA_PROBE_OBJECTS.length){
    host.appendChild(
      makeElement(
        "div",
        "source-picker-empty",
        "No se encontraron tablas disponibles."
      )
    );
    q("selectAllSources").disabled=true;
    syncProbeSelection();
    return;
  }

  for(const item of DATA_PROBE_OBJECTS){
    const qualified=String(
      item.qualified_name||
      (
        String(item.schema||"")+
        "."+
        String(item.name||"")
      )
    ).replace(/^\\./,"");

    if(!qualified)continue;

    const label=makeElement("label","source-option");
    const checkbox=document.createElement("input");
    checkbox.type="checkbox";
    checkbox.value=qualified;
    checkbox.onchange=syncProbeSelection;

    const text=makeElement(
      "span",
      "",
      qualified
    );

    label.append(checkbox,text);
    host.appendChild(label);
  }

  q("selectAllSources").disabled=
    !host.querySelector('input[type="checkbox"]');

  syncProbeSelection();
}

function invalidateDataProbe(){
  DATA_PROBE_VALID=false;
  DATA_PROBE_OBJECTS=[];
  q("connectionSources").value="";
  q("selectAllSources").disabled=true;
  q("createConnection").disabled=true;
  q("connectionSourceCount").textContent="Primero prueba la conexión.";

  const host=q("connectionSourcePicker");
  host.replaceChildren();
  host.appendChild(
    makeElement(
      "div",
      "source-picker-empty",
      "Las tablas disponibles aparecerán aquí después de verificar la conexión."
    )
  );
}

function showCreateConnection(show){
  q("createConnectionPanel").classList.toggle("hidden-panel",!show);

  if(show){
    q("connectionName").focus();
    return;
  }

  q("connectionName").value="";
  q("connectionServer").value="";
  q("connectionDatabase").value="";
  q("connectionUsername").value="";
  q("connectionPassword").value="";
  q("connectionSources").value="";
  q("connectionAccess").value="windows";
  q("connectionCredentials").classList.add("hidden-panel");
  status("connectionProbeStatus","","info");
  invalidateDataProbe();
}

function renderConnections(payload){
  const host=q("connectionsList");
  host.replaceChildren();

  const connections=
    Array.isArray(payload&&payload.connections)
      ? payload.connections
      : [];

  q("addConnectionButton").disabled=!DATA_CAPS.can_configure;

  if(!connections.length){
    host.appendChild(
      makeElement(
        "div",
        "item-meta",
        "Aún no hay conexiones para mostrar."
      )
    );
    syncProbeSelection();
    return;
  }

  for(const item of connections){
    const card=makeElement("article","user-card");
    card.appendChild(
      makeElement("div","user-name",item.name)
    );
    card.appendChild(
      makeElement("div","user-login",item.database||"")
    );

    const pill=makeElement(
      "span",
      "status-pill"+(item.enabled?"":" off"),
      item.status_label||"Requiere atención"
    );

    card.appendChild(pill);

    const actions=makeElement("div","user-actions");

    const test=makeElement(
      "button",
      "btn",
      "Probar conexión"
    );

    test.type="button";
    test.disabled=!DATA_CAPS.can_configure;
    test.onclick=()=>testConnection(item,test);

    const toggle=makeElement(
      "button",
      "btn",
      item.enabled?"Desactivar":"Activar"
    );

    toggle.type="button";
    toggle.disabled=!DATA_CAPS.can_configure;
    toggle.onclick=()=>toggleConnection(item,toggle);

    actions.append(test,toggle);
    card.appendChild(actions);
    host.appendChild(card);
  }

  syncProbeSelection();
}

async function loadConnections(){
  status("dataStatus","Cargando conexiones...","info");

  try{
    const r=await pf("/api/enterprise/data-connections");
    if(!r)return;

    const d=await r.json().catch(()=>({}));

    if(r.status===403){
      DATA_CAPS={can_configure:false};
      renderConnections({connections:[]});
      status(
        "dataStatus",
        "No tienes permiso para consultar las conexiones.",
        "info"
      );
      return;
    }

    if(!r.ok){
      status(
        "dataStatus",
        dataProbeError(d,"No se pudieron cargar las conexiones."),
        "error"
      );
      return;
    }

    DATA_CAPS={
      can_configure:Boolean(
        APP&&
        APP.capabilities&&
        APP.capabilities.configure_data
      )
    };

    renderConnections(d);
    status("dataStatus","Conexiones actualizadas.","success");
  }
  catch(_){
    status(
      "dataStatus",
      "No se pudo conectar con el servicio local.",
      "error"
    );
  }
}

async function probeConnection(){
  const button=q("probeConnection");
  const access=q("connectionAccess").value;
  const server=q("connectionServer").value.trim();
  const database=q("connectionDatabase").value.trim();
  const username=q("connectionUsername").value.trim();
  const password=q("connectionPassword").value;

  invalidateDataProbe();

  if(!server||!database){
    status(
      "connectionProbeStatus",
      "Indica el servidor y la base de datos.",
      "warning"
    );
    return;
  }

  if(access==="password"&&(!username||!password)){
    status(
      "connectionProbeStatus",
      "Indica el usuario y la contraseña para comprobar el acceso.",
      "warning"
    );
    return;
  }

  button.disabled=true;

  status(
    "connectionProbeStatus",
    "Comprobando acceso y buscando tablas...",
    "info"
  );

  try{
    const payload={
      server:server,
      database:database,
      authentication:access,
      trust_server_certificate:q("connectionTrustCertificate").checked
    };

    if(access==="password"){
      payload.username=username;
      payload.password=password;
    }

    const response=await pf(
      "/api/enterprise/data-connections/probe",
      {
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body:JSON.stringify(payload)
      }
    );

    if(!response)return;

    const data=await response.json().catch(()=>({}));

    if(!response.ok){
      status(
        "connectionProbeStatus",
        dataProbeError(
          data,
          "No se pudo verificar el acceso a los datos."
        ),
        "error"
      );
      return;
    }

    const objects=
      Array.isArray(data.objects)
        ? data.objects
        : [];

    DATA_PROBE_VALID=true;
    renderProbeSources(objects);

    status(
      "connectionProbeStatus",
      objects.length
        ? "Conexión verificada. Elige las tablas que deseas autorizar."
        : "La conexión funciona, pero no se encontraron tablas disponibles.",
      objects.length?"success":"warning"
    );
  }
  catch(_){
    status(
      "connectionProbeStatus",
      "No se pudo conectar con el servicio local.",
      "error"
    );
  }
  finally{
    button.disabled=false;
    q("connectionPassword").value=
      access==="password"
        ? q("connectionPassword").value
        : "";
  }
}

async function createConnection(){
  const button=q("createConnection");
  const access=q("connectionAccess").value;
  const password=q("connectionPassword").value;
  const sources=selectedProbeSources();

  const body={
    display_name:q("connectionName").value.trim(),
    server:q("connectionServer").value.trim(),
    database:q("connectionDatabase").value.trim(),
    authentication:access,
    trust_server_certificate:q("connectionTrustCertificate").checked,
    username:q("connectionUsername").value.trim()||null,
    password:password||null,
    allowed_sources:sources
  };

  if(!DATA_PROBE_VALID){
    status(
      "connectionProbeStatus",
      "Primero prueba la conexión y busca las tablas disponibles.",
      "warning"
    );
    return;
  }

  if(
    !body.display_name||
    !body.server||
    !body.database||
    !sources.length
  ){
    status(
      "connectionProbeStatus",
      "Escribe un nombre y selecciona al menos una fuente autorizada.",
      "warning"
    );
    return;
  }

  if(
    access==="password"&&
    (!body.username||!password)
  ){
    status(
      "connectionProbeStatus",
      "Indica el usuario y la contraseña para continuar.",
      "warning"
    );
    return;
  }

  button.disabled=true;

  status(
    "connectionProbeStatus",
    "Guardando la conexión...",
    "info"
  );

  try{
    const r=await pf(
      "/api/enterprise/data-connections",
      {
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body:JSON.stringify(body)
      }
    );

    if(!r)return;

    const d=await r.json().catch(()=>({}));

    if(!r.ok){
      status(
        "connectionProbeStatus",
        dataProbeError(
          d,
          "No se pudo guardar la conexión."
        ),
        "error"
      );
      return;
    }

    q("connectionPassword").value="";

    const connection=d&&d.connection;
    const handle=String(
      connection&&connection.handle||""
    );

    if(handle){
      const testResponse=await pf(
        "/api/enterprise/data-connections/"+
        encodeURIComponent(handle)+
        "/test",
        {method:"POST"}
      );

      if(!testResponse)return;

      const tested=
        await testResponse.json().catch(()=>({}));

      if(!testResponse.ok||tested.verified!==true){
        showCreateConnection(false);
        await loadConnections();

        status(
          "dataStatus",
          dataProbeError(
            tested,
            "La conexión se guardó, pero necesita volver a verificarse."
          ),
          "warning"
        );
        return;
      }
    }

    showCreateConnection(false);
    await loadConnections();

    status(
      "dataStatus",
      "Conexión guardada y verificada correctamente.",
      "success"
    );

    if(dataSetupMode()){
      window.location.assign("/settings?setup=ai");
    }
  }
  catch(_){
    q("connectionPassword").value="";

    status(
      "connectionProbeStatus",
      "No se pudo conectar con el servicio local.",
      "error"
    );
  }
  finally{
    button.disabled=false;
  }
}
async function toggleConnection(item,button){button.disabled=true;try{const r=await pf("/api/enterprise/data-connections/"+encodeURIComponent(item.handle)+"/status",{method:"PUT",headers:{"Content-Type":"application/json"},body:JSON.stringify({enabled:!item.enabled})});if(!r)return;const d=await r.json().catch(()=>({}));if(!r.ok){status("dataStatus",userError(d,"No se pudo cambiar el estado de la conexión."),"error");return}await loadConnections()}catch(_){status("dataStatus","No se pudo conectar con el servicio local.","error")}finally{button.disabled=false}}
async function testConnection(item,button){button.disabled=true;status("dataStatus","Verificando conexión...","info");try{const r=await pf("/api/enterprise/data-connections/"+encodeURIComponent(item.handle)+"/test",{method:"POST"});if(!r)return;const d=await r.json().catch(()=>({}));status("dataStatus",r.ok?"Conexión verificada.":userError(d,"No se pudo verificar la conexión."),r.ok?"success":"error");await loadConnections()}catch(_){status("dataStatus","No se pudo conectar con el servicio local.","error")}finally{button.disabled=false}}
q("accentColor").oninput=()=>q("accentText").textContent=q("accentColor").value.toUpperCase();
q("saveCompany").onclick=saveCompany;
q("companyTab").onclick=()=>showSettingsPanel("company");
q("usersTab").onclick=()=>showSettingsPanel("users");
q("dataTab").onclick=()=>showSettingsPanel("data");
q("aiTab").onclick=()=>showSettingsPanel("ai");
q("appearanceTab").onclick=()=>showSettingsPanel("appearance");
q("recoveryTab").onclick=()=>showSettingsPanel("recovery");
q("advancedTab").onclick=()=>showSettingsPanel("advanced");
q("addUserButton").onclick=()=>showCreateUser(true);
q("cancelCreate").onclick=()=>showCreateUser(false);
q("createUser").onclick=createUser;
q("addConnectionButton").onclick=()=>showCreateConnection(true);
q("cancelConnection").onclick=()=>showCreateConnection(false);
q("probeConnection").onclick=probeConnection;
q("createConnection").onclick=createConnection;
q("selectAllSources").onclick=()=>{
  for(const item of q("connectionSourcePicker").querySelectorAll('input[type="checkbox"]')){
    item.checked=true;
  }
  syncProbeSelection();
};
q("skipDataSetup").onclick=()=>window.location.assign("/settings?setup=ai");
q("connectionTrustCertificate").onchange=invalidateDataProbe;
q("connectionAccess").onchange=()=>{
  q("connectionCredentials").classList.toggle(
    "hidden-panel",
    q("connectionAccess").value!=="password"
  );
  invalidateDataProbe();
};
for(const id of [
  "connectionServer",
  "connectionDatabase",
  "connectionUsername",
  "connectionPassword"
]){
  q(id).addEventListener("input",invalidateDataProbe);
}
q("saveAi").onclick=saveAiConfiguration;
q("detectAi").onclick=detectAiModels;
q("testAi").onclick=testAiConfiguration;
q("aiEngine").addEventListener("change",invalidateAiVerification);
q("aiModel").addEventListener("change",invalidateAiVerification);
q("continueAiSetup").onclick=continueAiSetup;
q("refreshReady").onclick=loadReadySetup;
q("reviewSettings").onclick=()=>window.location.assign("/settings");
q("enterProduct").onclick=()=>window.location.assign("/app");
q("appearanceAccent").oninput=()=>q("appearanceAccentText").textContent=q("appearanceAccent").value.toUpperCase();
q("saveAppearance").onclick=saveAppearance;
q("createBackup").onclick=createBackup;
q("restoreBackup").onclick=restoreBackup;
q("saveAdvanced").onclick=saveAdvanced;
async function loadSettingsEntry(){
  const setup=
    new URLSearchParams(window.location.search).get("setup");

  if(setup==="data"){
    document.documentElement.classList.add("first-run-setup");
    q("firstRunDataGuide").classList.remove("hidden-panel");
    q("skipDataSetup").classList.remove("hidden-panel");
    showSettingsPanel("data");
    showCreateConnection(true);
    return;
  }

  if(setup==="ai"){
    document.documentElement.classList.add("first-run-setup");
    showSettingsPanel("ai");
    q("continueAiSetup").classList.remove("hidden-panel");
    return;
  }

  if(setup==="ready"){
    document.documentElement.classList.add("first-run-setup");
    showSettingsPanel("ready");
    return;
  }

  await loadCompany();
}
bind(loadSettingsEntry);
"""

PRODUCT_SETTINGS_HTML = page("Configuración", "settings", "Configuración", "Administra cómo funciona IA Empresarial Local en tu empresa.", SETTINGS_BODY, SETTINGS_JS)
