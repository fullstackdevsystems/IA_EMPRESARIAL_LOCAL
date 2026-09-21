from __future__ import annotations

PRODUCT_HOME_HTML = r"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light dark">
<title>IA Empresarial Local</title>
<style>
:root{
  --primary:#12355b;
  --accent:#0b8fa3;
  --bg:#f5f8fc;
  --surface:#ffffff;
  --surface-soft:#eef4f8;
  --border:#d7e1ea;
  --text:#172b4d;
  --muted:#64748b;
  --success:#16803c;
  --warning:#a86700;
  --danger:#b42318;
  --shadow:0 16px 42px rgba(16,35,58,.10);
  --radius:18px
}
*{box-sizing:border-box}
html,body{margin:0;min-height:100%;font-family:Segoe UI,Arial,sans-serif}
body{background:var(--bg);color:var(--text)}
button,input{font:inherit}
button,a{transition:transform .16s ease,box-shadow .16s ease,background .16s ease}
button:focus-visible,a:focus-visible,input:focus-visible{
  outline:3px solid color-mix(in srgb,var(--accent) 32%,transparent);
  outline-offset:2px
}
.shell{min-height:100vh;display:grid;grid-template-columns:245px minmax(0,1fr)}
.sidebar{
  background:linear-gradient(180deg,#10243d,#12355b);
  color:#fff;padding:24px 18px;display:flex;flex-direction:column;gap:24px
}
.brand{display:flex;align-items:center;gap:12px}
.brandmark{
  width:42px;height:42px;border-radius:13px;background:rgba(255,255,255,.14);
  display:grid;place-items:center;font-weight:800;font-size:18px
}
.brandname{font-weight:800;line-height:1.15}
.brandsub{font-size:12px;color:#cbd5e1;margin-top:3px}
.nav{display:grid;gap:7px}
.nav a{
  color:#dbe7f5;text-decoration:none;padding:11px 12px;border-radius:11px;
  display:flex;gap:10px;align-items:center;font-size:14px;min-height:44px
}
.nav a:hover,.nav a.active{background:rgba(255,255,255,.12);color:#fff}
.nav .icon{width:22px;text-align:center}
.sidebar-footer{margin-top:auto;font-size:12px;color:#bfd0e3;line-height:1.45}
.content{min-width:0}
.topbar{
  min-height:74px;padding:14px 28px;display:flex;align-items:center;
  justify-content:space-between;border-bottom:1px solid var(--border);
  background:color-mix(in srgb,var(--surface) 94%,transparent);
  position:sticky;top:0;z-index:20;backdrop-filter:blur(12px)
}
.companybox{display:flex;align-items:center;gap:11px}
.company-logo{
  width:40px;height:40px;border-radius:11px;object-fit:contain;
  background:var(--surface-soft);border:1px solid var(--border);padding:4px;display:none
}
.brandmark img{width:100%;height:100%;object-fit:contain;border-radius:10px}
.company{font-weight:800;font-size:17px}
.company-sub{font-size:12px;color:var(--muted);margin-top:2px}
.userbox{display:flex;align-items:center;gap:10px;position:relative}
.avatar{
  width:38px;height:38px;border-radius:50%;display:grid;place-items:center;
  background:var(--surface-soft);font-weight:800;color:var(--primary)
}
.user-meta{text-align:right}
.user-name{font-size:13px;font-weight:700}
.user-role{font-size:11px;color:var(--muted)}
.logout{
  border:1px solid var(--border);background:var(--surface);color:var(--text);
  padding:8px 11px;border-radius:10px;cursor:pointer
}
.profile-button{
  border:1px solid var(--border);background:var(--surface);color:var(--text);
  min-height:38px;padding:7px 10px;border-radius:10px;cursor:pointer;font-size:12px;font-weight:700;
  white-space:nowrap;
}
.profile-panel{
  position:absolute;right:54px;top:48px;width:260px;display:none;z-index:80;
  border:1px solid var(--border);border-radius:14px;background:var(--surface);
  box-shadow:var(--shadow);padding:15px
}
.profile-panel.show{display:block}
.profile-title{font-size:12px;color:var(--muted);margin-bottom:8px}
.profile-name{font-size:14px;font-weight:800}
.profile-role{font-size:12px;color:var(--muted);margin-top:3px}
.action[hidden]{display:none}
main{max-width:1380px;margin:0 auto;padding:38px 30px 54px}
.hero{display:flex;justify-content:space-between;gap:28px;align-items:flex-end;margin-bottom:26px}
.eyebrow{font-size:13px;font-weight:800;color:var(--accent);margin-bottom:7px}
h1{font-size:clamp(30px,4vw,46px);letter-spacing:-.035em;margin:0 0 8px}
.hero p{margin:0;color:var(--muted);font-size:16px}
.system-chip{
  border:1px solid var(--border);background:var(--surface);border-radius:999px;
  padding:9px 13px;font-size:12px;white-space:nowrap
}
.actions{
  display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:16px
}
.action{
  min-height:198px;text-decoration:none;color:var(--text);background:var(--surface);
  border:1px solid var(--border);border-radius:var(--radius);padding:21px;
  box-shadow:0 8px 26px rgba(16,35,58,.055);display:flex;flex-direction:column
}
.action:hover{transform:translateY(-2px);box-shadow:var(--shadow)}
.action-icon{
  width:44px;height:44px;border-radius:13px;background:var(--surface-soft);
  display:grid;place-items:center;font-size:21px;margin-bottom:19px
}
.action h2{font-size:18px;margin:0 0 8px}
.action p{font-size:13px;line-height:1.5;color:var(--muted);margin:0 0 18px}
.action-go{margin-top:auto;color:var(--accent);font-size:13px;font-weight:800}
.section-head{
  display:flex;align-items:center;justify-content:space-between;
  margin:34px 0 13px
}
.section-head h2{margin:0;font-size:18px}
.section-head span{font-size:12px;color:var(--muted)}
.status-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}
.status-card{
  border:1px solid var(--border);border-radius:15px;background:var(--surface);
  padding:15px 16px;display:flex;align-items:center;gap:12px
}
.status-dot{width:11px;height:11px;border-radius:50%;background:#94a3b8;flex:0 0 auto}
.status-dot.ok{background:var(--success)}
.status-dot.warn{background:var(--warning)}
.status-dot.bad{background:var(--danger)}
.status-label{font-size:12px;color:var(--muted)}
.status-value{font-size:13px;font-weight:800;margin-top:2px}
.admin-card{
  margin-top:16px;border:1px solid var(--border);background:linear-gradient(
  115deg,var(--surface),color-mix(in srgb,var(--accent) 6%,var(--surface)));
  border-radius:var(--radius);padding:18px 20px;display:none;
  align-items:center;justify-content:space-between;gap:20px
}
.admin-card.show{display:flex}
.admin-card h3{margin:0 0 5px;font-size:15px}
.admin-card p{margin:0;color:var(--muted);font-size:13px}
.admin-card a{
  text-decoration:none;background:var(--primary);color:white;
  border-radius:10px;padding:10px 13px;font-size:13px;font-weight:800;white-space:nowrap
}
#admin-card a{min-height:44px;display:inline-flex;align-items:center}.mobile-nav{display:none}
.loading{
  position:fixed;inset:0;background:var(--bg);z-index:1000;
  display:grid;place-items:center
}
.loading-card{text-align:center;color:var(--muted)}
.spinner{
  width:34px;height:34px;border-radius:50%;border:3px solid var(--border);
  border-top-color:var(--accent);animation:spin .8s linear infinite;margin:0 auto 12px
}
@keyframes spin{to{transform:rotate(360deg)}}
.auth{
  position:fixed;inset:0;z-index:1200;background:linear-gradient(145deg,#10243d,#12355b);
  display:none;place-items:center;padding:22px
}
.auth.show{display:grid}
.auth-card{
  width:min(430px,100%);background:#fff;color:#172b4d;border-radius:22px;
  padding:30px;box-shadow:0 26px 75px rgba(0,0,0,.3)
}
.auth-logo{
  width:48px;height:48px;border-radius:15px;background:#eef4f8;color:#12355b;
  display:grid;place-items:center;font-weight:900;margin-bottom:18px
}
.auth h2{margin:0 0 7px;font-size:24px}
.auth p{margin:0 0 20px;color:#64748b;line-height:1.45}
.auth label{display:block;font-size:12px;font-weight:700;margin:12px 0 6px}
.auth input{
  width:100%;border:1px solid #cbd5e1;border-radius:10px;padding:11px 12px;
  background:#fff;color:#172b4d
}
.auth button{
  width:100%;border:0;border-radius:10px;background:#12355b;color:#fff;
  padding:12px;margin-top:17px;font-weight:800;cursor:pointer
}
.auth-status{min-height:18px;margin-top:11px;font-size:12px;color:#b42318}
.first-run{
  display:none;margin-top:14px;padding:13px;border-radius:11px;
  background:#f8fafc;border:1px solid #e2e8f0;font-size:13px;line-height:1.45
}
.first-run.show{display:block}
.first-run a{font-weight:800;color:#12355b}
@media(max-width:1100px){
  .actions{grid-template-columns:repeat(2,minmax(0,1fr))}
  .status-grid{grid-template-columns:repeat(2,minmax(0,1fr))}
}
@media(max-width:820px){
  .shell{display:block;padding-bottom:70px}
  .sidebar{display:none}
  .topbar{padding:10px 14px;gap:10px}
  .company-sub,.user-role{display:none}
  .user-meta{display:none}
  main{padding:28px 16px 108px}
  .hero{display:block}
  .system-chip{display:inline-block;margin-top:16px}
  .mobile-nav{
    display:grid;grid-auto-flow:column;grid-auto-columns:1fr;position:fixed;z-index:50;
    bottom:0;left:0;right:0;background:var(--surface);border-top:1px solid var(--border);
    min-height:66px;padding-bottom:max(0px,env(safe-area-inset-bottom))
  }
  .mobile-nav a{
    text-decoration:none;color:var(--muted);font-size:10px;text-align:center;
    padding:9px 2px 6px
  }
  .mobile-nav a.active{color:var(--accent);font-weight:800}.mobile-nav b{display:block;font-size:19px;margin-bottom:3px}
}
@media(max-width:620px){
  .companybox{min-width:0;flex:1}
  .company{font-size:15px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:150px}
  .userbox{gap:7px;flex:0 0 auto}
  .profile-button{font-size:11px;padding:7px 8px}
  .profile-panel{right:0;width:min(280px,calc(100vw - 28px))}
  .actions,.status-grid{grid-template-columns:1fr}
  .action{min-height:164px}
  .admin-card{align-items:flex-start;flex-direction:column}
  .logout{font-size:12px;padding:7px 9px}
}
</style>
</head>
<body>

<div id="loading" class="loading">
  <div class="loading-card">
    <div class="spinner"></div>
    Preparando tu espacio de trabajo…
  </div>
</div>

<div id="auth" class="auth">
  <div class="auth-card">
    <div class="auth-logo">IA</div>
    <h2>Bienvenido</h2>
    <p>Accede a la información y herramientas de tu empresa.</p>

    <label for="login-user">Usuario</label>
    <input id="login-user" autocomplete="username">

    <label for="login-password">Contraseña</label>
    <input id="login-password" type="password" autocomplete="current-password">

    <button id="login-button" type="button">Entrar</button>
    <div id="auth-status" class="auth-status"></div>

    <div id="first-run" class="first-run">
      Esta instalación todavía necesita su configuración inicial.
      <a href="/">Configurar mi empresa</a>
    </div>
  </div>
</div>

<div id="product" class="shell" style="display:none">

  <aside class="sidebar">
    <div class="brand">
      <div class="brandmark" id="brand-mark">IA</div>
      <div>
        <div class="brandname" id="brand-name-side">IA Empresarial Local</div>
        <div class="brandsub">Inteligencia para tu empresa</div>
      </div>
    </div>

    <nav class="nav">
      <a class="active" href="/app"><span class="icon">⌂</span>Inicio</a>
      <a href="/assistant"><span class="icon">✦</span>Asistente</a>
      <a href="/analyze"><span class="icon">▤</span>Analizar</a>
      <a href="/data"><span class="icon">◫</span>Datos</a>
      <a href="/reports"><span class="icon">▥</span>Reportes</a>
      <a id="settings-nav" href="/settings" style="display:none">
        <span class="icon">⚙</span>Configuración
      </a>
    </nav>

    <div class="sidebar-footer">
      Tus datos permanecen dentro de la infraestructura configurada por tu empresa.
    </div>
  </aside>

  <div class="content">

    <header class="topbar">
      <div class="companybox">
        <img id="company-logo" class="company-logo" alt="">
        <div>
          <div id="company-name" class="company">IA Empresarial Local</div>
          <div class="company-sub">Espacio empresarial</div>
        </div>
      </div>

      <div class="userbox">
        <div class="user-meta">
          <div id="user-name" class="user-name">Usuario</div>
          <div id="user-role" class="user-role"></div>
        </div>
        <div id="avatar" class="avatar">U</div>
        <button id="profile-button" class="profile-button" type="button" aria-expanded="false" aria-controls="profile-panel">Mi perfil</button>
        <div id="profile-panel" class="profile-panel" aria-hidden="true">
          <div class="profile-title">Mi perfil</div>
          <div id="profile-name" class="profile-name">Usuario</div>
          <div id="profile-role" class="profile-role"></div>
        </div>
        <button class="logout" type="button" onclick="logout()">Salir</button>
      </div>
    </header>

    <main>
      <section class="hero">
        <div>
          <div class="eyebrow">TU ESPACIO DE TRABAJO</div>
          <h1 id="welcome">Hola.</h1>
          <p>¿Qué quieres hacer hoy?</p>
        </div>
        <div id="system-chip" class="system-chip">Comprobando estado…</div>
      </section>

      <section class="actions">

        <a class="action" href="/assistant">
          <div class="action-icon">✦</div>
          <h2>Preguntar a mi empresa</h2>
          <p>Haz preguntas sobre tus datos, documentos y conocimiento empresarial.</p>
          <div class="action-go">Abrir asistente →</div>
        </a>

        <a class="action" href="/analyze">
          <div class="action-icon">▤</div>
          <h2>Analizar un archivo</h2>
          <p>Carga un Excel o CSV y genera análisis, dashboard, PDF y Excel.</p>
          <div class="action-go">Comenzar análisis →</div>
        </a>

        <a class="action" href="/data">
          <div class="action-icon">◫</div>
          <h2>Consultar mis datos</h2>
          <p>Accede a las fuentes de información disponibles para tu empresa.</p>
          <div class="action-go">Ver información →</div>
        </a>

        <a class="action" href="/reports">
          <div class="action-icon">▥</div>
          <h2>Ver reportes</h2>
          <p>Consulta dashboards y resultados empresariales generados anteriormente.</p>
          <div class="action-go">Abrir reportes →</div>
        </a>

        <a id="connect-data-action" class="action" href="/settings?section=data" hidden>
          <div class="action-icon">↔</div>
          <h2>Conectar información</h2>
          <p>Agrega SQL Server u otras fuentes disponibles para tu empresa.</p>
          <div class="action-go">Configurar datos →</div>
        </a>

      </section>

      <div class="section-head">
        <h2>Estado de tu empresa</h2>
        <span>Resumen de preparación</span>
      </div>

      <section class="status-grid">
        <div class="status-card">
          <span id="dot-company" class="status-dot"></span>
          <div>
            <div class="status-label">Empresa</div>
            <div id="status-company" class="status-value">Comprobando…</div>
          </div>
        </div>

        <div class="status-card">
          <span id="dot-data" class="status-dot"></span>
          <div>
            <div class="status-label">Datos</div>
            <div id="status-data" class="status-value">Comprobando…</div>
          </div>
        </div>

        <div class="status-card">
          <span id="dot-ai" class="status-dot"></span>
          <div>
            <div class="status-label">Inteligencia artificial</div>
            <div id="status-ai" class="status-value">Comprobando…</div>
          </div>
        </div>

        <div class="status-card">
          <span id="dot-overall" class="status-dot"></span>
          <div>
            <div class="status-label">Sistema</div>
            <div id="status-overall" class="status-value">Comprobando…</div>
          </div>
        </div>
      </section>

      <section id="admin-card" class="admin-card">
        <div>
          <h3>Administrar la plataforma</h3>
          <p>Configura usuarios, datos, apariencia e inteligencia artificial.</p>
        </div>
        <a href="/settings">Abrir configuración</a>
      </section>

    </main>
  </div>
</div>

<nav class="mobile-nav" id="mobile-nav" style="display:none">
  <a class="active" href="/app"><b>⌂</b>Inicio</a>
  <a href="/assistant"><b>✦</b>Asistente</a>
  <a href="/analyze"><b>▤</b>Analizar</a>
  <a href="/data"><b>◫</b>Datos</a>
  <a href="/reports"><b>▥</b>Reportes</a>
  <a id="settings-mobile-nav" href="/settings" style="display:none"><b>⚙</b>Configuración</a>
</nav>

<script>
let token = sessionStorage.getItem('iaEnterpriseSession') || '';

const loading = document.getElementById('loading');
const auth = document.getElementById('auth');
const product = document.getElementById('product');
const firstRun = document.getElementById('first-run');
const authStatus = document.getElementById('auth-status');

function escapeText(value){
  return String(value == null ? '' : value);
}

function initials(value){
  const words = escapeText(value).trim().split(/\s+/).filter(Boolean);
  if(!words.length) return 'IA';
  return words.slice(0,2).map(x => x.charAt(0).toUpperCase()).join('');
}

function renderCompanyLogo(company,companyName){
  const logo = escapeText((company || {}).logo_reference).trim();
  const headerLogo = document.getElementById("company-logo");
  const brandMark = document.getElementById("brand-mark");

  const fallback = ()=>{
    headerLogo.removeAttribute("src");
    headerLogo.style.display = "none";
    headerLogo.alt = "";
    brandMark.replaceChildren(document.createTextNode(initials(companyName)));
  };

  fallback();
  if(!logo) return;

  headerLogo.alt = "Logo de " + companyName;
  headerLogo.onload = ()=>{headerLogo.style.display = "block"};
  headerLogo.onerror = fallback;
  headerLogo.src = logo;

  const sideLogo = document.createElement("img");
  sideLogo.alt = "";
  sideLogo.onload = ()=>{brandMark.replaceChildren(sideLogo)};
  sideLogo.onerror = ()=>{brandMark.replaceChildren(document.createTextNode(initials(companyName)))};
  sideLogo.src = logo;
}

function closeProfile(){
  const panel = document.getElementById("profile-panel");
  const button = document.getElementById("profile-button");
  panel.classList.remove("show");
  panel.setAttribute("aria-hidden","true");
  button.setAttribute("aria-expanded","false");
}

function toggleProfile(){
  const panel = document.getElementById("profile-panel");
  const button = document.getElementById("profile-button");
  const open = !panel.classList.contains("show");
  panel.classList.toggle("show",open);
  panel.setAttribute("aria-hidden",String(!open));
  button.setAttribute("aria-expanded",String(open));
}

function friendlyStatus(value){
  const status = escapeText(value).toUpperCase();

  if(status === 'READY') return ['Listo','ok'];
  if(status === 'TESTED') return ['Verificado','ok'];
  if(status === 'CONFIGURED') return ['Configurado','ok'];
  if(status === 'NOT_REQUIRED') return ['No requerido','ok'];
  if(status === 'DEGRADED') return ['Requiere atención','warn'];
  if(status === 'BLOCKED') return ['Requiere configuración','bad'];

  return ['Pendiente','warn'];
}

function paintStatus(name,value){
  const result = friendlyStatus(value);
  const label = document.getElementById('status-' + name);
  const dot = document.getElementById('dot-' + name);

  label.textContent = result[0];
  dot.className = 'status-dot ' + result[1];
}

function showLogin(message=''){
  loading.style.display = 'none';
  product.style.display = 'none';
  document.getElementById('mobile-nav').style.display = 'none';
  auth.classList.add('show');
  authStatus.textContent = message;
}

function showProduct(){
  auth.classList.remove('show');
  loading.style.display = 'none';
  product.style.display = '';
  document.getElementById('mobile-nav').removeAttribute('style');
}

async function detectFirstRun(){
  firstRun.classList.remove('show');

  try{
    const response = await fetch('/api/onboarding/status',{cache:'no-store'});

    if(response.ok){
      const data = await response.json();

      if(data.status === 'FIRST_RUN' && data.bootstrap_available){
        firstRun.classList.add('show');
      }
    }
  }catch(error){}
}

async function login(){
  const username = document.getElementById('login-user').value.trim();
  const password = document.getElementById('login-password');
  const button = document.getElementById('login-button');

  authStatus.textContent = '';

  if(!username || !password.value){
    authStatus.textContent = 'Escribe tu usuario y contraseña.';
    return;
  }

  button.disabled = true;

  try{
    const response = await fetch('/api/auth/login',{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({
        username:username,
        password:password.value
      })
    });

    let data = {};

    try{
      data = await response.json();
    }catch(error){}

    if(!response.ok || !data.token){
      throw new Error(
        (data.detail && (data.detail.message || data.detail.code))
        || 'No pudimos iniciar sesión.'
      );
    }

    token = String(data.token);
    sessionStorage.setItem('iaEnterpriseSession',token);
    password.value = '';

    await loadContext();

  }catch(error){
    token = '';
    sessionStorage.removeItem('iaEnterpriseSession');
    password.value = '';
    authStatus.textContent = String(error.message || error);
  }finally{
    button.disabled = false;
  }
}

async function logout(){
  try{
    if(token){
      await fetch('/api/auth/logout',{
        method:'POST',
        headers:{'Authorization':'Bearer ' + token}
      });
    }
  }catch(error){}

  token = '';
  sessionStorage.removeItem('iaEnterpriseSession');
  showLogin('Sesión cerrada.');
}

async function loadContext(){
  if(!token){
    showLogin();
    await detectFirstRun();
    return;
  }

  try{
    const response = await fetch('/api/enterprise/app-context',{
      headers:{'Authorization':'Bearer ' + token},
      cache:'no-store'
    });

    if(response.status === 401){
      token = '';
      sessionStorage.removeItem('iaEnterpriseSession');
      showLogin('Tu sesión terminó. Inicia sesión nuevamente.');
      return;
    }

    if(!response.ok){
      throw new Error('No pudimos preparar tu espacio de trabajo.');
    }

    const data = await response.json();

    const company = data.company || {};
    const user = data.user || {};
    const readiness = data.readiness || {};
    const steps = readiness.steps || {};
    const capabilities = data.capabilities || {};

    const companyName =
      escapeText(company.display_name).trim() || 'IA Empresarial Local';

    const displayName =
      escapeText(user.display_name).trim()
      || escapeText(user.username).trim()
      || 'Usuario';

    document.documentElement.style.setProperty(
      '--accent',
      company.accent_color || '#0b8fa3'
    );

    document.getElementById('company-name').textContent = companyName;
    document.getElementById('brand-name-side').textContent = companyName;
    renderCompanyLogo(company,companyName);

    document.getElementById('user-name').textContent = displayName;
    document.getElementById('user-role').textContent =
      escapeText(user.role_label);

    document.getElementById("profile-name").textContent = displayName;
    document.getElementById("profile-role").textContent =
      escapeText(user.role_label).trim() || "Usuario";

    document.getElementById('avatar').textContent = initials(displayName);
    document.getElementById('welcome').textContent = 'Hola, ' + displayName + '.';

    paintStatus('company',(steps.company || {}).status);
    paintStatus('data',(steps.sql || {}).status);
    paintStatus('ai',(steps.ai || {}).status);
    paintStatus('overall',readiness.status);

    const overall = friendlyStatus(readiness.status);
    document.getElementById('system-chip').textContent =
      'Sistema: ' + overall[0];

    document.getElementById("connect-data-action").hidden =
      !Boolean(capabilities.configure_data);

    const canOpenSettings = Boolean(capabilities.settings);
    document.getElementById("settings-nav").style.display =
      canOpenSettings ? "" : "none";
    document.getElementById("settings-mobile-nav").style.display =
      canOpenSettings ? "" : "none";
    document.getElementById("admin-card").classList.toggle(
      "show",
      canOpenSettings
    );

    showProduct();

  }catch(error){
    loading.style.display = 'none';
    showLogin('No pudimos cargar tu espacio de trabajo.');
  }
}

document.getElementById('login-button').addEventListener('click',login);

document.getElementById('login-password').addEventListener('keydown',event=>{
  if(event.key === 'Enter'){
    login();
  }
});

document.getElementById("profile-button").addEventListener("click",event=>{
  event.stopPropagation();
  toggleProfile();
});

document.getElementById("profile-panel").addEventListener("click",event=>{
  event.stopPropagation();
});

document.addEventListener("click",closeProfile);
document.addEventListener("keydown",event=>{
  if(event.key === "Escape") closeProfile();
});

loadContext();
</script>
</body>
</html>
"""
