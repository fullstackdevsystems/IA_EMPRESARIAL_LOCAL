from __future__ import annotations

PRODUCT_ASSISTANT_HTML = r"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light dark">
<title>Asistente | IA Empresarial Local</title>
<style>
:root{
  --primary:#12355b;
  --primary-2:#183f68;
  --accent:#0b8fa3;
  --bg:#f4f7fb;
  --surface:#ffffff;
  --surface-soft:#eef4f8;
  --border:#d8e2eb;
  --text:#172b4d;
  --muted:#66788f;
  --success:#16803c;
  --warning:#a86700;
  --danger:#b42318;
  --shadow:0 14px 34px rgba(16,35,58,.09);
  --radius:18px
}
*{box-sizing:border-box}
html,body{margin:0;min-height:100%;font-family:Segoe UI,Arial,sans-serif}
body{background:var(--bg);color:var(--text)}
button,input,textarea{font:inherit}
button,a{transition:transform .16s ease,box-shadow .16s ease,background .16s ease}
button:focus-visible,a:focus-visible,input:focus-visible,textarea:focus-visible{
  outline:3px solid color-mix(in srgb,var(--accent) 30%,transparent);
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
  display:grid;place-items:center;font-weight:800
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
.company{font-weight:800;font-size:17px}
.company-sub{font-size:12px;color:var(--muted);margin-top:2px}
.userbox{display:flex;align-items:center;gap:10px}
.user-meta{text-align:right}
.user-name{font-size:13px;font-weight:700}
.user-role{font-size:11px;color:var(--muted)}
.avatar{
  width:38px;height:38px;border-radius:50%;display:grid;place-items:center;
  background:var(--surface-soft);font-weight:800;color:var(--primary)
}
.logout{
  border:1px solid var(--border);background:var(--surface);color:var(--text);
  padding:8px 11px;border-radius:10px;cursor:pointer
}
main{
  max-width:1500px;margin:0 auto;padding:28px 30px 45px;
  display:grid;grid-template-columns:minmax(0,1fr) 330px;gap:20px
}
.assistant-column{min-width:0}
.hero{
  display:flex;align-items:flex-end;justify-content:space-between;
  gap:20px;margin-bottom:18px
}
.eyebrow{font-size:13px;font-weight:800;color:var(--accent);margin-bottom:6px}
h1{font-size:clamp(28px,3vw,40px);letter-spacing:-.035em;margin:0 0 7px}
.hero p{margin:0;color:var(--muted)}
.status-chip{
  border:1px solid var(--border);background:var(--surface);
  border-radius:999px;padding:8px 12px;font-size:12px;white-space:nowrap
}
.quick-prompts{
  display:flex;gap:8px;flex-wrap:wrap;margin:0 0 16px
}
.quick-prompts button{
  border:1px solid var(--border);background:var(--surface);color:var(--text);
  border-radius:999px;padding:8px 12px;cursor:pointer;font-size:12px
}
.quick-prompts button:hover{border-color:var(--accent);transform:translateY(-1px)}
.chat-card{
  min-height:640px;background:var(--surface);border:1px solid var(--border);
  border-radius:var(--radius);box-shadow:var(--shadow);
  display:flex;flex-direction:column;overflow:hidden
}
.messages{
  flex:1;min-height:430px;max-height:64vh;overflow:auto;
  padding:24px;background:linear-gradient(180deg,#fff,#fbfdff)
}
.empty-chat{
  height:100%;min-height:360px;display:grid;place-items:center;text-align:center;
  color:var(--muted);padding:25px
}
.empty-icon{
  width:58px;height:58px;margin:0 auto 14px;border-radius:17px;
  background:var(--surface-soft);display:grid;place-items:center;
  font-size:25px;color:var(--primary)
}
.empty-chat h2{margin:0 0 7px;color:var(--text);font-size:20px}
.empty-chat p{margin:0;max-width:520px;line-height:1.5}
.message{display:flex;margin:12px 0}
.message.user{justify-content:flex-end}
.bubble{
  max-width:min(790px,86%);padding:13px 15px;border-radius:15px;
  line-height:1.55;font-size:14px
}
.user .bubble{
  background:var(--primary);color:#fff;border-bottom-right-radius:5px
}
.assistant .bubble{
  background:var(--surface-soft);color:var(--text);border-bottom-left-radius:5px
}
.bubble p{margin:0 0 8px}
.bubble p:last-child{margin-bottom:0}
.bubble ul,.bubble ol{margin:7px 0 7px 22px;padding:0}
.bubble code{
  background:rgba(100,116,139,.14);padding:1px 4px;border-radius:4px;
  font-family:Consolas,monospace;font-size:12px
}
.answer-meta{
  margin-top:10px;padding-top:9px;border-top:1px solid rgba(100,116,139,.2);
  color:var(--muted);font-size:11px
}
.feedback{display:flex;gap:6px;margin-top:9px}
.feedback button{
  border:1px solid var(--border);background:var(--surface);border-radius:8px;
  padding:5px 8px;cursor:pointer;font-size:11px
}
.composer{
  border-top:1px solid var(--border);padding:14px;background:var(--surface);
  display:flex;gap:10px;align-items:flex-end
}
.composer textarea{
  flex:1;resize:none;min-height:54px;max-height:150px;
  border:1px solid var(--border);border-radius:13px;padding:14px;
  color:var(--text);background:#fff
}
.send,.stop{
  border:0;border-radius:12px;padding:12px 16px;color:#fff;
  font-weight:800;cursor:pointer;min-height:48px
}
.send{background:var(--primary)}
.stop{background:var(--danger);display:none}
.send:disabled,.stop:disabled{opacity:.55;cursor:not-allowed}
.composer-help{
  padding:0 14px 12px;color:var(--muted);font-size:11px
}
.side-stack{display:grid;gap:14px;align-content:start}
.side-card{
  background:var(--surface);border:1px solid var(--border);
  border-radius:var(--radius);padding:17px
}
.side-card h2{font-size:15px;margin:0 0 7px}
.side-card p{font-size:12px;line-height:1.45;color:var(--muted);margin:0}
.source-summary{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin:14px 0}
.mini-stat{
  background:var(--surface-soft);border-radius:12px;padding:11px
}
.mini-label{font-size:11px;color:var(--muted)}
.mini-value{font-size:20px;font-weight:800;margin-top:2px}
.upload{
  width:100%;border:1px dashed var(--border);border-radius:12px;
  padding:13px;background:#fbfdff;margin-top:10px
}
.upload input{width:100%;font-size:12px}
.upload button{
  width:100%;margin-top:8px;border:0;border-radius:9px;padding:9px;
  background:var(--primary);color:#fff;font-weight:700;cursor:pointer
}
.upload-status{font-size:11px;color:var(--muted);margin-top:8px;min-height:15px}
.source-list{margin-top:12px;display:grid;gap:6px}
.source-item{
  border:1px solid var(--border);border-radius:10px;padding:9px 10px;
  font-size:12px
}
.source-item small{display:block;color:var(--muted);margin-top:2px}
.source-empty{font-size:12px;color:var(--muted)}
.side-link{
  display:block;text-decoration:none;color:var(--accent);
  font-size:12px;font-weight:800;margin-top:12px
}
.notice{
  border-radius:12px;padding:11px 12px;font-size:12px;line-height:1.45;
  background:#f8fafc;border:1px solid var(--border)
}
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
.auth-status{min-height:18px;margin-top:11px;font-size:12px;color:var(--danger)}
.loading{
  position:fixed;inset:0;background:var(--bg);z-index:1000;
  display:grid;place-items:center;color:var(--muted)
}
.spinner{
  width:34px;height:34px;border-radius:50%;border:3px solid var(--border);
  border-top-color:var(--accent);animation:spin .8s linear infinite;margin:0 auto 12px
}
@keyframes spin{to{transform:rotate(360deg)}}
#settings-shortcut{min-height:44px;display:flex;align-items:center}.mobile-nav{display:none}
@media(max-width:1120px){
  main{grid-template-columns:1fr}
  .side-stack{grid-template-columns:repeat(2,minmax(0,1fr))}
}
@media(max-width:820px){
  .shell{display:block;padding-bottom:70px}
  main{padding-bottom:108px}
  .sidebar{display:none}
  .topbar{padding:12px 16px}
  .user-meta,.company-sub{display:none}
  main{padding:22px 14px 32px}
  .hero{display:block}
  .status-chip{display:inline-block;margin-top:12px}
  .side-stack{grid-template-columns:1fr}
  .chat-card{min-height:560px}
  .messages{max-height:58vh;padding:15px}
  .bubble{max-width:92%}
  .mobile-nav{
    display:grid;grid-auto-flow:column;grid-auto-columns:1fr;position:fixed;
    z-index:50;bottom:0;left:0;right:0;background:var(--surface);
    border-top:1px solid var(--border);min-height:66px;
    padding-bottom:max(0px,env(safe-area-inset-bottom))
  }
  .mobile-nav a{
    text-decoration:none;color:var(--muted);font-size:10px;text-align:center;
    padding:9px 2px 6px
  }
  .mobile-nav a.active{color:var(--accent);font-weight:800}
  .mobile-nav b{display:block;font-size:19px;margin-bottom:3px}
}
@media(max-width:560px){
  .quick-prompts{display:grid;grid-template-columns:1fr 1fr}
  .composer{align-items:stretch}
  .composer textarea{min-height:64px}
  .send,.stop{padding:10px 12px}
}
</style>
</head>
<body>

<div id="loading" class="loading">
  <div>
    <div class="spinner"></div>
    Preparando tu asistente…
  </div>
</div>

<div id="auth" class="auth">
  <div class="auth-card">
    <div class="auth-logo">IA</div>
    <h2>Bienvenido</h2>
    <p>Accede para conversar con la información disponible de tu empresa.</p>

    <label for="login-user">Usuario</label>
    <input id="login-user" autocomplete="username">

    <label for="login-password">Contraseña</label>
    <input id="login-password" type="password" autocomplete="current-password">

    <button id="login-button" type="button">Entrar</button>
    <div id="auth-status" class="auth-status"></div>
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
      <a href="/app"><span class="icon">⌂</span>Inicio</a>
      <a class="active" href="/assistant"><span class="icon">✦</span>Asistente</a>
      <a href="/analyze"><span class="icon">▤</span>Analizar</a>
      <a href="/data"><span class="icon">◫</span>Datos</a>
      <a href="/reports"><span class="icon">▥</span>Reportes</a>
      <a id="settings-nav" href="/settings" style="display:none">
        <span class="icon">⚙</span>Configuración
      </a>
    </nav>

    <div class="sidebar-footer">
      Tus preguntas utilizan únicamente la información y permisos disponibles para tu empresa.
    </div>
  </aside>

  <div class="content">
    <header class="topbar">
      <div>
        <div id="company-name" class="company">IA Empresarial Local</div>
        <div class="company-sub">Asistente empresarial</div>
      </div>

      <div class="userbox">
        <div class="user-meta">
          <div id="user-name" class="user-name">Usuario</div>
          <div id="user-role" class="user-role"></div>
        </div>
        <div id="avatar" class="avatar">U</div>
        <button class="logout" type="button" onclick="logout()">Salir</button>
      </div>
    </header>

    <main>
      <section class="assistant-column">
        <div class="hero">
          <div>
            <div class="eyebrow">ASISTENTE EMPRESARIAL</div>
            <h1>Pregunta a tu empresa</h1>
            <p>Consulta información, documentos y conocimiento empresarial desde un solo lugar.</p>
          </div>
          <div id="system-chip" class="status-chip">Preparando…</div>
        </div>

        <div class="quick-prompts">
          <button type="button" onclick="usePrompt('Dame un resumen ejecutivo de la información disponible.')">
            Resumen ejecutivo
          </button>
          <button type="button" onclick="usePrompt('¿Qué información importante debería revisar hoy?')">
            Qué revisar hoy
          </button>
          <button type="button" onclick="usePrompt('Identifica tendencias, cambios o anomalías relevantes.')">
            Tendencias y alertas
          </button>
          <button type="button" onclick="usePrompt('Explícame qué información tienes disponible sobre mi empresa.')">
            Información disponible
          </button>
        </div>

        <section class="chat-card">
          <div id="messages" class="messages">
            <div id="empty-chat" class="empty-chat">
              <div>
                <div class="empty-icon">✦</div>
                <h2>¿Qué necesitas saber?</h2>
                <p>
                  Puedes preguntar con lenguaje normal. El asistente utilizará la información
                  empresarial disponible de acuerdo con tus permisos.
                </p>
              </div>
            </div>
          </div>

          <div class="composer">
            <textarea
              id="question"
              placeholder="Escribe una pregunta sobre tu empresa…"
              disabled
            ></textarea>

            <button id="send" class="send" type="button" disabled>
              Enviar
            </button>

            <button id="stop" class="stop" type="button">
              Detener
            </button>
          </div>

          <div class="composer-help">
            Presiona Ctrl + Enter para enviar.
          </div>
        </section>
      </section>

      <aside class="side-stack">

        <section class="side-card">
          <h2>Información disponible</h2>
          <p>
            El asistente puede utilizar los archivos y datos autorizados para tu empresa.
          </p>

          <div class="source-summary">
            <div class="mini-stat">
              <div class="mini-label">Documentos</div>
              <div id="document-count" class="mini-value">0</div>
            </div>

            <div class="mini-stat">
              <div class="mini-label">Datos</div>
              <div id="dataset-count" class="mini-value">0</div>
            </div>
          </div>

          <div class="upload">
            <input
              id="source-file"
              type="file"
              accept=".csv,.xlsx,.xls,.xlsm,.xlsb,.pdf,.docx,.txt,.md,.markdown"
            >
            <button id="upload-button" type="button">Agregar información</button>
            <div id="upload-status" class="upload-status"></div>
          </div>

          <div id="source-list" class="source-list"></div>
        </section>

        <section class="side-card">
          <h2>Estado</h2>
          <div id="readiness-note" class="notice">
            Comprobando preparación…
          </div>
          <a id="settings-shortcut" class="side-link" href="/settings" style="display:none">
            Revisar configuración →
          </a>
        </section>

        <section class="side-card">
          <h2>Privacidad empresarial</h2>
          <p>
            La información mostrada depende de tu empresa, usuario y permisos asignados.
          </p>
        </section>

      </aside>
    </main>
  </div>
</div>

<nav class="mobile-nav" id="mobile-nav" style="display:none">
  <a href="/app"><b>⌂</b>Inicio</a>
  <a class="active" href="/assistant"><b>✦</b>Asistente</a>
  <a href="/analyze"><b>▤</b>Analizar</a>
  <a href="/data"><b>◫</b>Datos</a>
  <a href="/reports"><b>▥</b>Reportes</a>
  <a id="settings-mobile-nav" href="/settings" style="display:none"><b>⚙</b>Configuración</a>
</nav>

<script>
let token = sessionStorage.getItem('iaEnterpriseSession') || '';
let currentUser = null;
let activeController = null;
let historyItems = [];

const loading = document.getElementById('loading');
const auth = document.getElementById('auth');
const product = document.getElementById('product');
const authStatus = document.getElementById('auth-status');
const messages = document.getElementById('messages');
const question = document.getElementById('question');
const sendButton = document.getElementById('send');
const stopButton = document.getElementById('stop');

function text(value){
  return String(value == null ? '' : value);
}

function initials(value){
  const words = text(value).trim().split(/\s+/).filter(Boolean);
  if(!words.length) return 'IA';
  return words.slice(0,2).map(x => x.charAt(0).toUpperCase()).join('');
}

function escapeHtml(value){
  return text(value).replace(/[&<>"']/g, char => ({
    '&':'&amp;',
    '<':'&lt;',
    '>':'&gt;',
    '"':'&quot;',
    "'":'&#39;'
  })[char]);
}

function renderAnswer(value){
  let safe = escapeHtml(value);

  safe = safe
    .replace(/```([\s\S]*?)```/g,'<pre><code>$1</code></pre>')
    .replace(/`([^`]+)`/g,'<code>$1</code>')
    .replace(/\*\*([^*]+)\*\*/g,'<strong>$1</strong>')
    .replace(/\n\n+/g,'</p><p>')
    .replace(/\n/g,'<br>');

  return '<p>' + safe + '</p>';
}

function friendlyStatus(value){
  const status = text(value).toUpperCase();

  if(status === 'READY') return 'Listo';
  if(status === 'TESTED') return 'Verificado';
  if(status === 'CONFIGURED') return 'Configurado';
  if(status === 'NOT_REQUIRED') return 'No requerido';
  if(status === 'DEGRADED') return 'Requiere atención';
  if(status === 'BLOCKED') return 'Requiere configuración';

  return 'Pendiente';
}

function showLogin(message=''){
  if(activeController){
    activeController.abort();
    activeController = null;
  }

  loading.style.display = 'none';
  product.style.display = 'none';
  document.getElementById('mobile-nav').style.display = 'none';
  auth.classList.add('show');
  authStatus.textContent = message;
  question.disabled = true;
  sendButton.disabled = true;
}

function showProduct(){
  auth.classList.remove('show');
  loading.style.display = 'none';
  product.style.display = '';
  document.getElementById('mobile-nav').removeAttribute('style');
  question.disabled = false;
  sendButton.disabled = false;
}

async function protectedFetch(url,options={}){
  const headers = {
    ...(options.headers || {}),
    'Authorization':'Bearer ' + token
  };

  const response = await fetch(url,{
    ...options,
    headers
  });

  if(response.status === 401){
    token = '';
    sessionStorage.removeItem('iaEnterpriseSession');
    showLogin('Tu sesión terminó. Inicia sesión nuevamente.');
    return null;
  }

  return response;
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
        username,
        password:password.value
      })
    });

    let payload = {};

    try{
      payload = await response.json();
    }catch(error){}

    if(!response.ok || !payload.token){
      throw new Error(
        payload.detail && (
          payload.detail.message
          || payload.detail.code
        )
        || 'Credenciales inválidas.'
      );
    }

    token = text(payload.token);
    sessionStorage.setItem('iaEnterpriseSession',token);
    password.value = '';

    await establishSession();

  }catch(error){
    token = '';
    sessionStorage.removeItem('iaEnterpriseSession');
    password.value = '';
    authStatus.textContent = text(error.message || error);
  }finally{
    button.disabled = false;
  }
}

async function logout(){
  try{
    if(token){
      await protectedFetch('/api/auth/logout',{
        method:'POST'
      });
    }
  }catch(error){}

  token = '';
  currentUser = null;
  sessionStorage.removeItem('iaEnterpriseSession');
  showLogin('Sesión cerrada.');
}

async function establishSession(){
  if(!token){
    showLogin();
    return false;
  }

  try{
    const response = await protectedFetch(
      '/api/enterprise/app-context',
      {cache:'no-store'}
    );

    if(!response) return false;

    if(!response.ok){
      throw new Error('No pudimos preparar tu asistente.');
    }

    const context = await response.json();

    currentUser = context.user || {};

    const company = context.company || {};
    const readiness = context.readiness || {};
    const capabilities = context.capabilities || {};

    const companyName =
      text(company.display_name).trim()
      || 'IA Empresarial Local';

    const displayName =
      text(currentUser.display_name).trim()
      || text(currentUser.username).trim()
      || 'Usuario';

    document.documentElement.style.setProperty(
      '--accent',
      company.accent_color || '#0b8fa3'
    );

    document.getElementById('company-name').textContent = companyName;
    document.getElementById('brand-name-side').textContent = companyName;
    document.getElementById('brand-mark').textContent = initials(companyName);

    document.getElementById('user-name').textContent = displayName;
    document.getElementById('user-role').textContent =
      text(currentUser.role_label);

    document.getElementById('avatar').textContent = initials(displayName);

    document.getElementById('system-chip').textContent =
      'Sistema: ' + friendlyStatus(readiness.status);

    const readinessText = friendlyStatus(readiness.status);

    document.getElementById('readiness-note').textContent =
      readinessText === 'Listo'
      ? 'Tu empresa está lista para trabajar.'
      : 'Hay elementos de configuración pendientes. Puedes seguir usando las funciones disponibles.';

    if(capabilities.settings){
      document.getElementById('settings-nav').style.display = '';
      document.getElementById('settings-mobile-nav').style.display = '';
      document.getElementById('settings-shortcut').style.display = '';
    }

    showProduct();

    await refreshSources();

    return true;

  }catch(error){
    showLogin('No pudimos validar tu sesión.');
    return false;
  }
}

function clearEmpty(){
  const empty = document.getElementById('empty-chat');

  if(empty){
    empty.remove();
  }
}

function addMessage(kind,content){
  clearEmpty();

  const row = document.createElement('div');
  row.className = 'message ' + kind;

  const bubble = document.createElement('div');
  bubble.className = 'bubble';

  if(kind === 'assistant'){
    bubble.innerHTML = renderAnswer(content);
  }else{
    bubble.textContent = content;
  }

  row.appendChild(bubble);
  messages.appendChild(row);
  messages.scrollTop = messages.scrollHeight;

  return bubble;
}

function renderSourceSummary(event){
  const sources = Array.isArray(event.sources)
    ? event.sources
    : [];

  if(!sources.length){
    return 'Respuesta generada con la información disponible.';
  }

  const labels = [];

  for(const source of sources){
    const type = text(source.type);

    if(type === 'document'){
      labels.push('Documento: ' + text(source.file || source.name || 'fuente'));
    }else if(type === 'dataset'){
      labels.push('Datos: ' + text(source.file || source.name || 'fuente'));
    }else if(type === 'connected_data'){
      labels.push(
        'Datos conectados: '
        + text(source.resource || source.name || 'fuente')
      );
    }else if(type === 'memory'){
      labels.push('Conocimiento empresarial');
    }else if(type === 'model_knowledge'){
      labels.push('Conocimiento general');
    }
  }

  return [...new Set(labels)].join(' · ')
    || 'Respuesta generada con la información disponible.';
}

function renderAnswerKind(event){
  const retrieval = event && event.retrieval || {};
  if(retrieval.structured || retrieval.fast_path === 'governed_sql'){
    return 'Hecho calculado · basado en información verificada';
  }
  return 'Interpretación asistida · revisa las fuentes indicadas';
}

function addFeedback(bubble,event,answer){
  const container = document.createElement('div');
  container.className = 'feedback';

  const positive = document.createElement('button');
  positive.type = 'button';
  positive.textContent = '👍 Útil';

  const negative = document.createElement('button');
  negative.type = 'button';
  negative.textContent = '👎 Corregir';

  positive.onclick = async () => {
    positive.disabled = true;
    negative.disabled = true;

    const response = await protectedFetch(
      '/api/enterprise/feedback',
      {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({
          feedback_type:'CORRECTO',
          target_type:'chat',
          target_ref:event.request_id || null,
          original_text:answer,
          source_context:{
            sources:event.sources || []
          }
        })
      }
    );

    if(response && response.ok){
      container.textContent = 'Gracias por tu valoración.';
    }else{
      container.textContent = 'No pudimos guardar la valoración.';
    }
  };

  negative.onclick = async () => {
    const correction = prompt(
      '¿Qué debería corregirse en la respuesta?'
    );

    if(!correction) return;

    positive.disabled = true;
    negative.disabled = true;

    const response = await protectedFetch(
      '/api/enterprise/feedback',
      {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({
          feedback_type:'REQUIERE_CORRECCION',
          target_type:'chat',
          target_ref:event.request_id || null,
          original_text:answer,
          correction_text:correction,
          proposal_type:'auto',
          source_context:{
            sources:event.sources || []
          }
        })
      }
    );

    if(response && response.ok){
      container.textContent = 'Corrección registrada para revisión.';
    }else{
      container.textContent = 'No pudimos guardar la corrección.';
    }
  };

  container.append(positive,negative);
  bubble.appendChild(container);
}

async function send(){
  const message = question.value.trim();

  if(!message || !token || activeController){
    return;
  }

  addMessage('user',message);
  question.value = '';

  sendButton.disabled = true;
  stopButton.style.display = '';
  activeController = new AbortController();

  const bubble = addMessage(
    'assistant',
    'Preparando respuesta…'
  );

  let answer = '';
  let completed = false;

  try{
    const response = await protectedFetch(
      '/api/enterprise/chat/stream',
      {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({
          message,
          history:historyItems.slice(-6)
        }),
        signal:activeController.signal
      }
    );

    if(!response) return;

    if(response.status === 403){
      bubble.textContent =
        'Tu usuario no tiene permiso para realizar esta consulta.';
      return;
    }

    if(!response.ok){
      let payload = {};

      try{
        payload = await response.json();
      }catch(error){}

      throw new Error(
        payload.detail
        || payload.error
        || 'No pudimos generar la respuesta.'
      );
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while(true){
      const chunk = await reader.read();

      if(chunk.done) break;

      buffer += decoder.decode(
        chunk.value,
        {stream:true}
      );

      const lines = buffer.split('\n');
      buffer = lines.pop();

      for(const line of lines){
        if(!line.trim()) continue;

        const event = JSON.parse(line);

        if(event.type === 'status'){
          if(!answer){
            bubble.textContent =
              event.message || 'Preparando respuesta…';
          }
          continue;
        }

        if(event.type === 'first_token'){
          continue;
        }

        if(event.type === 'token'){
          answer += event.text || '';
          bubble.innerHTML = renderAnswer(answer);
          messages.scrollTop = messages.scrollHeight;
          continue;
        }

        if(event.type === 'error'){
          throw new Error(
            event.message || 'No pudimos generar la respuesta.'
          );
        }

        if(event.type === 'done'){
          completed = true;
          answer = event.answer || answer;

          bubble.innerHTML = renderAnswer(answer);

          const meta = document.createElement('div');
          meta.className = 'answer-meta';
          meta.textContent = renderSourceSummary(event);
          bubble.appendChild(meta);

          const kind = document.createElement('div');
          kind.className = 'answer-meta';
          kind.textContent = renderAnswerKind(event);
          bubble.appendChild(kind);

          addFeedback(
            bubble,
            event,
            answer
          );

          historyItems.push(
            {role:'user',content:message},
            {role:'assistant',content:answer}
          );

          messages.scrollTop = messages.scrollHeight;
        }
      }
    }

    if(!completed && answer){
      const meta = document.createElement('div');
      meta.className = 'answer-meta';
      meta.textContent = 'Respuesta parcial.';
      bubble.appendChild(meta);
    }

  }catch(error){
    if(error.name === 'AbortError'){
      if(answer){
        bubble.innerHTML = renderAnswer(answer);

        const meta = document.createElement('div');
        meta.className = 'answer-meta';
        meta.textContent = 'Respuesta detenida.';
        bubble.appendChild(meta);
      }else{
        bubble.textContent = 'Respuesta detenida.';
      }
    }else{
      bubble.textContent =
        'No pudimos completar la respuesta: '
        + text(error.message || error);
    }
  }finally{
    activeController = null;
    sendButton.disabled = false;
    stopButton.style.display = 'none';
    question.focus();
  }
}

function stopGeneration(){
  if(activeController){
    activeController.abort();
  }
}

function usePrompt(value){
  question.value = value;
  question.focus();
}

function loadPromptFromUrl(){
  const params = new URLSearchParams(window.location.search);
  const value = (params.get('prompt') || '').trim();

  if(!value) return;

  question.value = value;
  question.focus();
}

function renderSources(documents,datasets){
  document.getElementById('document-count').textContent =
    String(documents.length);

  document.getElementById('dataset-count').textContent =
    String(datasets.length);

  const host = document.getElementById('source-list');
  host.replaceChildren();

  const combined = [];

  for(const item of documents.slice(0,4)){
    combined.push({
      title:item.name || 'Documento',
      kind:'Documento'
    });
  }

  for(const item of datasets.slice(0,4)){
    combined.push({
      title:item.name || 'Datos',
      kind:'Datos estructurados'
    });
  }

  if(!combined.length){
    const empty = document.createElement('div');
    empty.className = 'source-empty';
    empty.textContent = 'Aún no hay información agregada.';
    host.appendChild(empty);
    return;
  }

  for(const item of combined.slice(0,6)){
    const row = document.createElement('div');
    row.className = 'source-item';

    const title = document.createElement('strong');
    title.textContent = item.title;

    const kind = document.createElement('small');
    kind.textContent = item.kind;

    row.append(title,kind);
    host.appendChild(row);
  }
}

async function refreshConnectedSources(){
  let connections = [];

  try{
    const response = await protectedFetch(
      '/api/enterprise/data-connections',
      {cache:'no-store'}
    );

    if(!response || !response.ok){
      return;
    }

    const payload = await response.json();

    connections = (
      Array.isArray(payload.connections)
      ? payload.connections
      : []
    ).filter(item =>
      item
      && item.enabled !== false
      && item.read_only !== false
    );

  }catch(error){
    return;
  }

  if(!connections.length){
    return;
  }

  const countNode =
    document.getElementById('dataset-count');

  const host =
    document.getElementById('source-list');

  if(countNode){
    const baseCount =
      Number(countNode.textContent || '0');

    countNode.textContent = String(
      (
        Number.isFinite(baseCount)
        ? baseCount
        : 0
      )
      + connections.length
    );
  }

  if(!host){
    return;
  }

  const empty =
    host.querySelector('.source-empty');

  if(empty){
    empty.remove();
  }

  for(const item of connections.slice(0,4)){
    const row =
      document.createElement('div');

    row.className = 'source-item';
    row.dataset.connectedSource = 'true';

    const title =
      document.createElement('strong');

    title.textContent =
      text(item.display_name).trim()
      || text(item.name).trim()
      || 'Conexión empresarial';

    const kind =
      document.createElement('small');

    kind.textContent =
      'Datos conectados';

    row.append(
      title,
      kind
    );

    host.appendChild(row);
  }
}

async function refreshSources(){
  try{
    const responses = await Promise.all([
      protectedFetch('/api/enterprise/documents'),
      protectedFetch('/api/enterprise/datasets')
    ]);

    if(!responses[0] || !responses[1]){
      return;
    }

    if(
      responses[0].status === 403
      || responses[1].status === 403
    ){
      renderSources([],[]);
      return;
    }

    if(!responses[0].ok || !responses[1].ok){
      renderSources([],[]);
      return;
    }

    const payloads = await Promise.all([
      responses[0].json(),
      responses[1].json()
    ]);

    renderSources(
      Array.isArray(payloads[0].documents)
        ? payloads[0].documents
        : [],
      Array.isArray(payloads[1].datasets)
        ? payloads[1].datasets
        : []
    );

    await refreshConnectedSources();

  }catch(error){
    renderSources([],[]);
  }
}

async function uploadSource(){
  const input = document.getElementById('source-file');
  const button = document.getElementById('upload-button');
  const status = document.getElementById('upload-status');
  const file = input.files[0];

  if(!file){
    status.textContent = 'Selecciona un archivo.';
    return;
  }

  button.disabled = true;
  status.textContent = 'Agregando información…';

  try{
    const form = new FormData();
    form.append('file',file);
    form.append('scope','company');

    const response = await protectedFetch(
      '/api/enterprise/documents',
      {
        method:'POST',
        body:form
      }
    );

    if(!response) return;

    if(response.status === 403){
      status.textContent =
        'Tu usuario no tiene permiso para agregar información.';
      return;
    }

    if(!response.ok){
      status.textContent =
        'No pudimos agregar este archivo.';
      return;
    }

    input.value = '';
    status.textContent = 'Información agregada correctamente.';

    await refreshSources();

  }catch(error){
    status.textContent =
      'No pudimos agregar este archivo.';
  }finally{
    button.disabled = false;
  }
}

document.getElementById('login-button').addEventListener(
  'click',
  login
);

document.getElementById('login-password').addEventListener(
  'keydown',
  event => {
    if(event.key === 'Enter'){
      login();
    }
  }
);

sendButton.addEventListener(
  'click',
  send
);

stopButton.addEventListener(
  'click',
  stopGeneration
);

document.getElementById('upload-button').addEventListener(
  'click',
  uploadSource
);

question.addEventListener(
  'keydown',
  event => {
    if(event.ctrlKey && event.key === 'Enter'){
      send();
    }
  }
);

loadPromptFromUrl();
establishSession();
</script>
</body>
</html>
"""
