from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from .factory import build_components
from .security import Principal, ensure_secret, safe_component, verify_token


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=20000)
    history: List[Dict[str, str]] = Field(default_factory=list)


class MemoryCreateRequest(BaseModel):
    content: str = Field(min_length=1, max_length=12000)
    category: str = "conocimiento_empresa"
    scope: str = "company"
    confidence: float = 0.8
    importance: float = 0.6
    tags: List[str] = Field(default_factory=list)
    expires_at: Optional[str] = None


class MemoryUpdateRequest(BaseModel):
    content: Optional[str] = None
    category: Optional[str] = None
    confidence: Optional[float] = None
    importance: Optional[float] = None
    tags: Optional[List[str]] = None
    expires_at: Optional[str] = None
    active: Optional[bool] = None


class SettingsRequest(BaseModel):
    llm_provider: Optional[str] = None
    ollama_model: Optional[str] = None
    lmstudio_model: Optional[str] = None
    embedding_provider: Optional[str] = None
    embedding_model: Optional[str] = None
    embedding_lmstudio_model: Optional[str] = None
    max_memories: Optional[int] = None
    max_document_chunks: Optional[int] = None
    max_context_chars: Optional[int] = None
    generation_mode: Optional[str] = None
    num_ctx: Optional[int] = None
    detailed_num_ctx: Optional[int] = None
    max_concurrent_generations: Optional[int] = None
    queue_timeout_seconds: Optional[int] = None
    open_terminal_enabled: Optional[bool] = None
    warmup_llm: Optional[bool] = None


ASSISTANT_HTML = r"""
<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>IA Empresarial V8 - Asistente</title>
<style>body{margin:0;background:#f4f7fb;color:#142033;font-family:Segoe UI,Arial,sans-serif}.wrap{max-width:1100px;margin:28px auto;padding:0 18px}.card{background:#fff;border:1px solid #dbe3ee;border-radius:16px;box-shadow:0 10px 34px #2342a315;padding:22px}.head{display:flex;justify-content:space-between;gap:12px;align-items:center}.badge{background:#dbeafe;color:#1d4ed8;padding:5px 9px;border-radius:999px;font-size:12px}.msgs{height:52vh;overflow:auto;border:1px solid #dbe3ee;border-radius:12px;padding:14px;background:#fbfdff;margin:18px 0}.m{padding:11px 13px;border-radius:12px;margin:8px 0}.u{white-space:pre-wrap}.u{background:#e8f0ff;margin-left:16%}.a{background:#eefbf3;margin-right:10%}.src{font-size:12px;color:#506176;border-top:1px dashed #ccd5e0;margin-top:8px;padding-top:7px}.row{display:flex;gap:10px}.row textarea{flex:1;min-height:80px;padding:12px;border:1px solid #cbd5e1;border-radius:10px}.btn{border:0;background:#2563eb;color:white;border-radius:10px;padding:0 18px;font-weight:700;cursor:pointer}.stop{background:#b91c1c;display:none}.status{font-size:12px;color:#64748b;margin-top:6px}.warn{background:#fff7ed;border:1px solid #fed7aa;border-radius:10px;padding:10px;margin:10px 0}.links a{margin-left:12px;color:#1d4ed8;text-decoration:none}.a p{margin:0 0 9px}.a p:last-child{margin-bottom:0}.a h3,.a h4{margin:10px 0 6px}.a ul,.a ol{margin:7px 0 7px 22px;padding:0}.a li{margin:3px 0}.a code{background:#e2e8f0;padding:1px 4px;border-radius:4px;font-family:Consolas,monospace}.a pre{background:#0f172a;color:#e2e8f0;padding:10px;border-radius:8px;overflow:auto;white-space:pre-wrap}</style></head>
<body><div class="wrap"><div class="card"><div class="head"><div><h2 style="margin:0">Asistente Empresarial Local <span class="badge">V8.5.5 Base Productiva + Streaming</span></h2><div style="color:#64748b">Memoria persistente, documentos fundamentados y cálculos determinísticos.</div></div><div class="links"><a href="/">Analizador</a><a id="admin" href="/admin">Administración</a></div></div><div id="auth" class="warn" style="display:none">Falta token de acceso. Abre esta pantalla con <b>ABRIR_ASISTENTE.bat</b>.</div><div id="msgs" class="msgs"></div><div class="row"><textarea id="q" placeholder="Pregunta sobre documentos, reglas del negocio o datasets..."></textarea><button class="btn" id="send">Enviar</button><button class="btn stop" id="stop">Detener</button></div></div></div>
<script>
const hp=new URLSearchParams(location.hash.replace(/^#/,'')),ht=hp.get('token')||'';if(ht){localStorage.setItem('iaToken',ht);history.replaceState(null,'',location.pathname)}const token=ht||localStorage.getItem('iaToken')||'';if(!token)document.getElementById('auth').style.display='block';document.getElementById('admin').href='/admin#token='+encodeURIComponent(token);
let hist=[];const msgs=document.getElementById('msgs');
function escHtml(x){return String(x??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]))}
function md(text){
  const lines=escHtml(text).replace(/\r/g,'').split('\n');let out='',list=null,para=[];
  const flushP=()=>{if(para.length){out+='<p>'+para.join('<br>')+'</p>';para=[]}};
  const closeList=()=>{if(list){out+='</'+list+'>';list=null}};
  const inline=x=>x.replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>').replace(/`([^`]+)`/g,'<code>$1</code>');
  let inCode=false,code=[];
  for(const raw of lines){const line=raw.trimEnd();
    if(line.trim().startsWith('```')){flushP();closeList();if(inCode){out+='<pre><code>'+code.join('\n')+'</code></pre>';code=[]}inCode=!inCode;continue}
    if(inCode){code.push(line);continue}
    if(!line.trim()){flushP();closeList();continue}
    let m=line.match(/^###\s+(.+)/);if(m){flushP();closeList();out+='<h4>'+inline(m[1])+'</h4>';continue}
    m=line.match(/^##?\s+(.+)/);if(m){flushP();closeList();out+='<h3>'+inline(m[1])+'</h3>';continue}
    m=line.match(/^[-*]\s+(.+)/);if(m){flushP();if(list!=='ul'){closeList();out+='<ul>';list='ul'}out+='<li>'+inline(m[1])+'</li>';continue}
    m=line.match(/^\d+[.)]\s+(.+)/);if(m){flushP();if(list!=='ol'){closeList();out+='<ol>';list='ol'}out+='<li>'+inline(m[1])+'</li>';continue}
    closeList();para.push(inline(line));
  }
  if(inCode){out+='<pre><code>'+code.join('\n')+'</code></pre>'}flushP();closeList();return out;
}
function add(cls,text,extra=''){const d=document.createElement('div');d.className='m '+cls;if(cls==='a')d.innerHTML=md(text);else d.textContent=text;if(extra){const s=document.createElement('div');s.className='src';s.innerHTML=extra;d.appendChild(s)}msgs.appendChild(d);msgs.scrollTop=msgs.scrollHeight;return d}
let activeController=null;
function sourceHtml(d){let src=(d.sources||[]).map(x=>{if(x.type==='dataset')return 'Dataset: '+escHtml(x.file)+' | '+escHtml(x.sheet||'')+' | filas usadas: '+escHtml(x.rows_used??'N/D');if(x.type==='memory')return 'Memoria: '+escHtml(x.category)+' | '+escHtml(x.source_type||'fuente local');if(x.type==='model_knowledge')return 'Conocimiento general: '+escHtml(x.provider||'modelo local')+' / '+escHtml(x.model||'N/D');if(x.type==='system_capabilities')return 'Capacidades del sistema: configuración local verificada | '+escHtml(x.model||'N/D');return 'Documento: '+escHtml(x.file)+(x.page?' | pág. '+escHtml(x.page):'')+(x.sheet?' | hoja '+escHtml(x.sheet):'')+(x.rows?' | filas '+escHtml(x.rows):'')}).join('<br>');if(d.retrieval&&d.retrieval.response_profile){src+=(src?'<br>':'')+'Respuesta: '+escHtml(d.retrieval.response_profile);const cr=d.retrieval.completion_reason||'natural';if(cr==='natural')src+=' | finalización natural';else if(cr==='complete')src+=' | información del sistema completa';else if(cr==='continued_to_eos')src+=' | continuada automáticamente hasta completar';else if(cr==='repetition_guard_stop')src+=' | continuación detenida por repetición';else if(cr==='technical_context_stop')src+=' | límite técnico de contexto alcanzado';else if(cr==='operational_safety_stop')src+=' | detenida por salvaguarda operativa';if((d.retrieval.continuations||0)>0)src+=' | continuaciones: '+escHtml(d.retrieval.continuations);const cp=d.retrieval.context_plan;if(cp&&cp.num_ctx)src+=' | contexto dinámico: '+escHtml(cp.num_ctx);}if(d.timings_ms){if(d.timings_ms.first_token_ms!=null&&d.timings_ms.first_token_ms>0)src+=(src?'<br>':'')+'Primer token: '+escHtml(d.timings_ms.first_token_ms)+' ms';if(d.timings_ms.queue_ms!=null&&d.timings_ms.queue_ms>0)src+=(src?'<br>':'')+'Cola: '+escHtml(d.timings_ms.queue_ms)+' ms';src+=(src?'<br>':'')+'Tiempo total: '+escHtml(d.timings_ms.total_ms??'N/D')+' ms'}if(d.request_id)src+=(src?'<br>':'')+'Solicitud: '+escHtml(d.request_id);return src}
async function send(){const q=document.getElementById('q');const m=q.value.trim();if(!m||!token||activeController)return;add('u',m);q.value='';const btn=document.getElementById('send'),stop=document.getElementById('stop');btn.disabled=true;stop.style.display='block';activeController=new AbortController();const bubble=add('a','Preparando respuesta...');let answer='',done=false;const t0=Date.now();const setStatus=t=>{if(!answer){bubble.textContent=t}else{let st=bubble.querySelector('.stream-status');if(!st){st=document.createElement('div');st.className='status stream-status';bubble.appendChild(st)}st.textContent=t}};try{const r=await fetch('/api/enterprise/chat/stream',{method:'POST',headers:{'Content-Type':'application/json','Authorization':'Bearer '+token},body:JSON.stringify({message:m,history:hist.slice(-6)}),signal:activeController.signal});if(!r.ok){let d={};try{d=await r.json()}catch{}throw new Error(d.detail||d.error||'Error '+r.status)}const reader=r.body.getReader(),dec=new TextDecoder();let buf='';while(true){const x=await reader.read();if(x.done)break;buf+=dec.decode(x.value,{stream:true});let lines=buf.split('\n');buf=lines.pop();for(const line of lines){if(!line.trim())continue;const ev=JSON.parse(line);if(ev.type==='status'){setStatus(ev.message+' '+Math.floor((Date.now()-t0)/1000)+' s');continue}if(ev.type==='first_token'){setStatus('Generando... primer token en '+ev.first_token_ms+' ms');continue}if(ev.type==='token'){answer+=ev.text;bubble.innerHTML=md(answer);msgs.scrollTop=msgs.scrollHeight;continue}if(ev.type==='error'){throw new Error(ev.message||'No se pudo generar la respuesta')}if(ev.type==='done'){done=true;answer=ev.answer||answer;bubble.innerHTML=md(answer);const src=document.createElement('div');src.className='src';src.innerHTML=sourceHtml(ev);bubble.appendChild(src);hist.push({role:'user',content:m},{role:'assistant',content:answer});msgs.scrollTop=msgs.scrollHeight;continue}}}if(!done&&answer){const src=document.createElement('div');src.className='src';src.textContent='Respuesta parcial.';bubble.appendChild(src)}}catch(e){if(e.name==='AbortError'){if(answer){bubble.innerHTML=md(answer);const src=document.createElement('div');src.className='src';src.textContent='Generación detenida por el usuario.';bubble.appendChild(src)}else bubble.textContent='Generación detenida por el usuario.'}else{bubble.textContent='ERROR: '+e.message}}finally{activeController=null;btn.disabled=false;stop.style.display='none'}}
function stopGeneration(){if(activeController)activeController.abort()}
async function confirmMem(id){const r=await fetch('/api/enterprise/memories/'+id+'/confirm',{method:'POST',headers:{'Authorization':'Bearer '+token}});alert(r.ok?'Memoria confirmada':'No se pudo confirmar')}
document.getElementById('send').onclick=send;document.getElementById('stop').onclick=stopGeneration;document.getElementById('q').addEventListener('keydown',e=>{if(e.ctrlKey&&e.key==='Enter')send()});
</script></body></html>
"""


ADMIN_HTML = r"""
<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>IA Empresarial V8 - Administración</title>
<style>body{margin:0;background:#f4f7fb;color:#142033;font-family:Segoe UI,Arial,sans-serif}.wrap{max-width:1240px;margin:26px auto;padding:0 18px}.card{background:#fff;border:1px solid #dbe3ee;border-radius:14px;padding:20px;margin:14px 0;box-shadow:0 8px 28px #2342a312}.grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}input,select,textarea{width:100%;box-sizing:border-box;padding:9px;border:1px solid #cbd5e1;border-radius:8px}.btn{background:#2563eb;color:#fff;border:0;border-radius:8px;padding:8px 12px;cursor:pointer;margin:2px}.muted{background:#64748b}.danger{background:#b91c1c}.ok{background:#15803d}.item{border-bottom:1px solid #e5e7eb;padding:10px 0}.small{font-size:12px;color:#64748b}.top a{margin-left:12px;color:#1d4ed8;text-decoration:none}.pill{font-size:11px;background:#e2e8f0;border-radius:999px;padding:3px 7px}.row{display:flex;gap:8px;align-items:center}.settings{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}.notice{background:#eff6ff;border:1px solid #bfdbfe;border-radius:8px;padding:9px;margin:8px 0}.search{margin:8px 0}@media(max-width:900px){.grid,.settings{grid-template-columns:1fr}}</style></head>
<body><div class="wrap"><div class="top" style="text-align:right"><a id="assistant" href="/assistant">Asistente</a><a href="/">Analizador</a></div><h2>Administración de conocimiento <span class="pill">V8.5.5 Base Productiva + Streaming</span></h2>
<div id="auth" class="notice" style="display:none">Falta token. Abre <b>ABRIR_ADMIN_MEMORIA_RAG.bat</b>.</div>
<div class="grid"><div class="card"><h3>Memoria permanente</h3><input class="search" id="mf" placeholder="Filtrar recuerdos..." oninput="renderMemories()"><textarea id="mc" placeholder="Regla, definición o conocimiento estable"></textarea><div class="row" style="margin-top:8px"><select id="cat"><option>regla_negocio</option><option>conocimiento_empresa</option><option>procedimiento</option><option>producto</option><option>proveedor</option><option>cliente</option><option>preferencia</option><option>definicion</option><option>operacion</option><option>instruccion</option></select><select id="mscope"><option value="company">Empresa</option><option value="user">Solo usuario</option></select><button class="btn" onclick="addMemory()">Crear</button></div><div id="mems"></div></div>
<div class="card"><h3>Conocimiento documental</h3><input id="doc" type="file" accept=".pdf,.xlsx,.xls,.xlsm,.xlsb,.csv,.docx,.txt,.md,.markdown"><div class="row" style="margin-top:8px"><select id="scope"><option value="company">Empresa</option><option value="user">Solo usuario</option></select><button class="btn" onclick="uploadDoc()">Indexar</button></div><div class="small" style="margin-top:7px">PDF, Word, Excel, CSV, TXT y Markdown. El hash evita reindexaciones innecesarias; las nuevas versiones reemplazan los fragmentos obsoletos.</div><div id="docs"></div></div></div>
<div class="card"><h3>Configuración IA</h3><div class="settings"><label>Proveedor LLM<select id="llmp"><option value="ollama">Ollama</option><option value="lmstudio">LM Studio</option></select></label><label>Modelo Ollama<input id="ollamam"></label><label>Modelo LM Studio<input id="lmm"></label><label>Finalización de respuesta<select id="genmode"><option value="natural">Natural (hasta completar)</option></select></label><label>Contexto base LLM (tokens)<input id="numctx" type="number" min="2048" max="32768"></label><label>Contexto detallado LLM (tokens)<input id="detailctx" type="number" min="4096" max="65536"></label><label>Generaciones concurrentes<input id="maxgen" type="number" min="1" max="8"></label><label>Espera máxima de cola (s)<input id="queuetimeout" type="number" min="5" max="600"></label><label>Precalentar LLM<select id="warmup"><option value="true">Sí</option><option value="false">No</option></select></label><label>Open Terminal<select id="open_terminal"><option value="false">Desactivado</option><option value="true">Activado</option></select></label><label>Proveedor embeddings<select id="embp"><option value="ollama">Ollama</option><option value="lmstudio">LM Studio</option></select></label><label>Modelo embeddings Ollama<input id="embm"></label><label>Modelo embeddings LM Studio<input id="emblm"></label><label>Máx. recuerdos<input id="maxm" type="number" min="1" max="50"></label><label>Máx. fragmentos RAG<input id="maxr" type="number" min="1" max="50"></label><label>Límite contexto (caracteres)<input id="maxc" type="number" min="2000" max="100000"></label></div><button class="btn" style="margin-top:10px" onclick="saveSettings()">Guardar configuración</button><div id="vector" class="small" style="margin-top:8px"></div><div class="small">Los cambios de proveedor/modelos requieren reiniciar la IA.</div></div>
<div class="grid"><div class="card"><h3>Datasets estructurados</h3><div id="datasets"></div></div><div class="card"><h3>Diagnóstico de producción</h3><button class="btn muted" onclick="loadDiagnostics()">Actualizar diagnóstico</button><div id="diag"></div></div></div><div class="card"><h3>Auditoría</h3><button class="btn muted" onclick="loadAudit()">Actualizar auditoría</button><div id="audit"></div></div></div>
<script>
const hp=new URLSearchParams(location.hash.replace(/^#/,'')),ht=hp.get('token')||'';if(ht){localStorage.setItem('iaToken',ht);history.replaceState(null,'',location.pathname)}const token=ht||localStorage.getItem('iaToken')||'';if(!token)document.getElementById('auth').style.display='block';document.getElementById('assistant').href='/assistant#token='+encodeURIComponent(token);const H={'Authorization':'Bearer '+token};let MEM=[];
async function j(url,opt={}){opt.headers={...(opt.headers||{}),...H};const r=await fetch(url,opt);let d={};try{d=await r.json()}catch{}if(!r.ok)throw new Error(d.detail||d.error||'Error '+r.status);return d}
function esc(x){return String(x??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]))}
function renderMemories(){const f=(mf.value||'').toLowerCase();mems.innerHTML=MEM.filter(x=>(x.content+' '+x.category+' '+(x.tags||[]).join(' ')).toLowerCase().includes(f)).map(x=>`<div class=item><b>${esc(x.category)}</b> <span class=pill>${esc(x.status)} | v${x.version} | importancia ${Number(x.importance).toFixed(2)}</span><br>${esc(x.content)}<div class=small>Fuente: ${esc(x.source_type||'N/D')}${x.source_ref?' / '+esc(x.source_ref):''} | actualizado: ${esc(x.updated_at||'')}</div><button class=btn onclick="editM('${x.id}')">Editar</button>${x.status==='pending'?`<button class="btn ok" onclick="confirmM('${x.id}')">Confirmar</button>`:''}${x.active?`<button class="btn muted" onclick="toggleM('${x.id}',false)">Desactivar</button>`:`<button class="btn ok" onclick="toggleM('${x.id}',true)">Activar</button>`}<button class="btn danger" onclick="forget('${x.id}')">Olvidar</button></div>`).join('')||'<div class=small>Sin memorias.</div>'}
async function load(){try{const [m,d,c,ds]=await Promise.all([j('/api/enterprise/memories?include_inactive=true'),j('/api/enterprise/documents'),j('/api/enterprise/settings'),j('/api/enterprise/datasets')]);MEM=m.memories;renderMemories();docs.innerHTML=d.documents.map(x=>`<div class=item><b>${esc(x.name)}</b> <span class=pill>v${x.current_version} | ${esc(x.status)} | ${x.chunk_count??0} fragmentos</span><div class=small>${esc(x.extension)} | ${(Number(x.size_bytes||0)/1048576).toFixed(2)} MB | actualizado ${esc(x.updated_at||'')}</div><button class=btn onclick="reindex('${x.id}')">Reindexar</button><button class="btn danger" onclick="delDoc('${x.id}')">Eliminar</button></div>`).join('')||'<div class=small>Sin documentos.</div>';llmp.value=c.llm.provider||'ollama';ollamam.value=c.llm.ollama_model||'';lmm.value=c.llm.lmstudio_model||'';genmode.value=c.llm.generation_mode||'natural';numctx.value=c.llm.num_ctx||4096;detailctx.value=c.llm.detailed_num_ctx||16384;maxgen.value=(c.runtime&&c.runtime.max_concurrent_generations)||1;queuetimeout.value=(c.runtime&&c.runtime.queue_timeout_seconds)||120;warmup.value=String((c.runtime&&c.runtime.warmup_llm)!==false);open_terminal.value=String(Boolean(c.runtime&&c.runtime.open_terminal_enabled));embp.value=c.embeddings.provider||'ollama';embm.value=c.embeddings.model||'';emblm.value=c.embeddings.lmstudio_model||'';maxm.value=c.retrieval.max_memories||6;maxr.value=c.retrieval.max_document_chunks||8;maxc.value=c.retrieval.max_context_chars||18000;vector.textContent='Vector store activo: '+(c.vector.backend_active||'N/D')+' | solicitado: '+(c.vector.backend||'N/D');datasets.innerHTML=ds.datasets.map(x=>`<div class=item><b>${esc(x.name)}</b><div class=small>${esc((x.columns||[]).join(', '))}</div></div>`).join('')||'<div class=small>Sin datasets registrados.</div>';await Promise.all([loadAudit(),loadDiagnostics()])}catch(e){alert(e.message)}}
async function addMemory(){if(!mc.value.trim())return;await j('/api/enterprise/memories',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({content:mc.value,category:cat.value,scope:mscope.value})});mc.value='';await load()}
async function editM(id){const x=MEM.find(v=>v.id===id);if(!x)return;const content=prompt('Contenido de la memoria:',x.content);if(content===null||!content.trim())return;const importance=prompt('Importancia 0.0 a 1.0:',x.importance);const confidence=prompt('Confianza 0.0 a 1.0:',x.confidence);await j('/api/enterprise/memories/'+id,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({content,importance:Number(importance),confidence:Number(confidence)})});await load()}
async function toggleM(id,active){await j('/api/enterprise/memories/'+id,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({active,status:active?'active':'inactive'})});await load()}
async function forget(id){if(confirm('¿Olvidar esta memoria?')){await j('/api/enterprise/memories/'+id,{method:'DELETE'});await load()}}async function confirmM(id){await j('/api/enterprise/memories/'+id+'/confirm',{method:'POST'});await load()}
async function uploadDoc(){const f=doc.files[0];if(!f)return;const fd=new FormData();fd.append('file',f);fd.append('scope',scope.value);await j('/api/enterprise/documents',{method:'POST',body:fd});doc.value='';await load()}
async function reindex(id){await j('/api/enterprise/documents/'+id+'/reindex',{method:'POST'});await load()}async function delDoc(id){if(confirm('¿Eliminar este documento y sus embeddings?')){await j('/api/enterprise/documents/'+id,{method:'DELETE'});await load()}}
async function saveSettings(){const body={llm_provider:llmp.value,ollama_model:ollamam.value,lmstudio_model:lmm.value,generation_mode:genmode.value,num_ctx:Number(numctx.value),detailed_num_ctx:Number(detailctx.value),max_concurrent_generations:Number(maxgen.value),queue_timeout_seconds:Number(queuetimeout.value),warmup_llm:warmup.value==='true',open_terminal_enabled:open_terminal.value==='true',embedding_provider:embp.value,embedding_model:embm.value,embedding_lmstudio_model:emblm.value,max_memories:Number(maxm.value),max_document_chunks:Number(maxr.value),max_context_chars:Number(maxc.value)};const d=await j('/api/enterprise/settings',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});alert(d.restart_required?'Guardado. Reinicia la IA para aplicar modelos/proveedor.':'Guardado')}
async function loadAudit(){try{const d=await j('/api/enterprise/audit?limit=20');audit.innerHTML=d.events.map(x=>`<div class=item><b>${esc(x.event_type)}</b> <span class=small>${esc(x.timestamp)}</span><br><span class=small>${esc(x.object_type||'')} ${esc(x.object_id||'')} | ${esc(x.outcome)}</span></div>`).join('')||'<div class=small>Sin eventos.</div>'}catch(e){audit.innerHTML='<div class=small>'+esc(e.message)+'</div>'}}
async function loadDiagnostics(){try{const d=await j('/api/enterprise/diagnostics');const q=d.recent_queries||{},p=d.providers||{},c=d.counts||{};diag.innerHTML=`<div class=item><b>LLM:</b> ${esc(p.llm)} / ${esc(p.model)} <span class=pill>${p.llm_healthy?'OK':'NO DISPONIBLE'}</span><br><span class=small>Vector: ${esc(d.storage&&d.storage.vector_store)} | memorias: ${esc(c.memories||0)} | documentos: ${esc(c.documents||0)} | datasets: ${esc(c.datasets||0)}</span></div><div class=item><b>Últimas consultas:</b> ${esc(q.count||0)}<br><span class=small>Promedio total: ${esc(q.avg_total_ms??'N/D')} ms | primer token: ${esc(q.avg_first_token_ms??'N/D')} ms | cola: ${esc(q.avg_queue_ms??'N/D')} ms</span></div>`}catch(e){diag.innerHTML='<div class=small>'+esc(e.message)+'</div>'}}
load();
</script></body></html>
"""


def install_enterprise_routes(app, root: str | Path):
    components = build_components(root)
    security_cfg = components.cfg.section("security")
    secret = ensure_secret(security_cfg["token_secret_file"])
    router = APIRouter()

    def principal_dependency(authorization: Optional[str] = Header(default=None)) -> Principal:
        raw = None
        if authorization and authorization.lower().startswith("bearer "):
            raw = authorization.split(" ", 1)[1].strip()
        if not raw:
            raise HTTPException(status_code=401, detail="Token requerido")
        try:
            return verify_token(secret, raw)
        except ValueError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc

    def admin_dependency(principal: Principal = Depends(principal_dependency)) -> Principal:
        if principal.role != "admin":
            raise HTTPException(status_code=403, detail="Se requiere rol admin")
        return principal

    @router.get("/assistant", response_class=HTMLResponse)
    def assistant_page():
        return ASSISTANT_HTML

    @router.get("/admin", response_class=HTMLResponse)
    def admin_page():
        return ADMIN_HTML

    @router.get("/api/enterprise/health/live")
    def enterprise_live():
        return {"ok": True, "version": "8.5.5", "status": "live"}

    @router.get("/api/enterprise/health/ready")
    def enterprise_ready():
        db_ok = True
        try:
            components.db.one("SELECT 1")
        except Exception:
            db_ok = False
        llm_ok = bool(components.llm.healthy())
        ok = db_ok and llm_ok
        return JSONResponse({"ok": ok, "version": "8.5.5", "status": "ready" if ok else "degraded", "database": db_ok, "llm": llm_ok, "vector_store": type(components.vectors).__name__}, status_code=200 if ok else 503)

    @router.get("/api/enterprise/diagnostics")
    def enterprise_diagnostics(principal: Principal = Depends(admin_dependency)):
        recent = components.db.query("SELECT total_ms,first_token_ms,queue_ms,status,route FROM query_metrics WHERE company_id=? ORDER BY id DESC LIMIT 20", (principal.company_id,))
        ok_rows = [r for r in recent if r["status"] == "ok"]
        avg = lambda key: round(sum(float(r[key] or 0) for r in ok_rows) / len(ok_rows), 2) if ok_rows else None
        return {
            "ok": True, "version": "8.5.5",
            "providers": {"llm": getattr(components.llm, "name", "unknown"), "model": getattr(components.llm, "model", None), "llm_healthy": components.llm.healthy(), "embeddings": getattr(components.embeddings, "model", "unknown")},
            "runtime": components.cfg.section("runtime"),
            "storage": {"database": str(components.cfg.database_path), "vector_store": type(components.vectors).__name__, "knowledge_dir": str(components.cfg.knowledge_dir)},
            "counts": {"memories": len(components.memory.list(principal, include_inactive=True)), "documents": len(components.documents.list(principal)), "datasets": len(components.datasets.list(principal))},
            "recent_queries": {"count": len(recent), "avg_total_ms": avg("total_ms"), "avg_first_token_ms": avg("first_token_ms"), "avg_queue_ms": avg("queue_ms")},
        }

    @router.get("/api/enterprise/health")
    def enterprise_health(principal: Principal = Depends(principal_dependency)):
        return {
            "ok": True,
            "version": "8.5.5",
            "company": principal.company_id,
            "user": principal.user_id,
            "llm_provider": getattr(components.llm, "name", "unknown"),
            "llm_model": getattr(components.llm, "model", None),
            "llm_healthy": components.llm.healthy(),
            "embedding_model": getattr(components.embeddings, "model", "unknown"),
            "vector_store": type(components.vectors).__name__,
        }

    @router.post("/api/enterprise/chat")
    def enterprise_chat(body: ChatRequest, principal: Principal = Depends(principal_dependency)):
        try:
            return components.service.chat(principal, body.message, body.history)
        except Exception as exc:
            components.db.audit("chat.http_error", principal.company_id, principal.user_id, "query", outcome="error", details={"error_type": type(exc).__name__})
            components.logger.exception("chat http error", extra={"event": "chat.http_error", "company_id": principal.company_id, "user_id": principal.user_id, "error_type": type(exc).__name__})
            return JSONResponse({"ok": False, "error": "No se pudo completar la solicitud con el servicio local."}, status_code=500)

    @router.post("/api/enterprise/chat/stream")
    def enterprise_chat_stream(body: ChatRequest, principal: Principal = Depends(principal_dependency)):
        def events():
            try:
                streamed = False
                for event in components.service.stream_general(principal, body.message, body.history):
                    if event.get("type") == "fallback":
                        break
                    streamed = True
                    yield json.dumps(event, ensure_ascii=False) + "\n"
                if not streamed:
                    yield json.dumps({"type": "status", "phase": "retrieval", "message": "Consultando evidencia empresarial..."}, ensure_ascii=False) + "\n"
                    result = components.service.chat(principal, body.message, body.history)
                    result = {**result, "type": "done"}
                    yield json.dumps(result, ensure_ascii=False) + "\n"
            except GeneratorExit:
                raise
            except Exception as exc:
                components.db.audit("chat.stream_error", principal.company_id, principal.user_id, "query", outcome="error", details={"error_type": type(exc).__name__})
                components.logger.exception("chat stream error", extra={"event": "chat.stream_error", "company_id": principal.company_id, "user_id": principal.user_id, "error_type": type(exc).__name__})
                yield json.dumps({"type": "error", "message": "No se pudo completar la respuesta con el servicio local."}, ensure_ascii=False) + "\n"
        return StreamingResponse(events(), media_type="application/x-ndjson", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    @router.get("/api/enterprise/memories")
    def list_memories(include_inactive: bool = False, principal: Principal = Depends(principal_dependency)):
        return {"memories": components.memory.list(principal, include_inactive=include_inactive)}

    @router.get("/api/enterprise/memories/search")
    def search_memories(q: str, limit: int = 20, principal: Principal = Depends(principal_dependency)):
        return {"memories": components.memory.search(principal, q, limit=max(1, min(limit, 50)), min_score=0.0)}

    @router.post("/api/enterprise/memories")
    def create_memory(body: MemoryCreateRequest, principal: Principal = Depends(principal_dependency)):
        return components.memory.create(
            principal, body.content, body.category, scope=body.scope, confidence=body.confidence,
            importance=body.importance, tags=body.tags, expires_at=body.expires_at,
        )

    @router.patch("/api/enterprise/memories/{memory_id}")
    def update_memory(memory_id: str, body: MemoryUpdateRequest, principal: Principal = Depends(principal_dependency)):
        changes = {key: value for key, value in body.model_dump().items() if value is not None}
        try:
            return components.memory.update(principal, memory_id, **changes)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.post("/api/enterprise/memories/{memory_id}/confirm")
    def confirm_memory(memory_id: str, principal: Principal = Depends(principal_dependency)):
        try:
            return components.memory.confirm(principal, memory_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.delete("/api/enterprise/memories/{memory_id}")
    def forget_memory(memory_id: str, principal: Principal = Depends(principal_dependency)):
        try:
            components.memory.forget(principal, memory_id)
            return {"ok": True}
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.post("/api/enterprise/documents")
    async def upload_document(file: UploadFile = File(...), scope: str = Form("company"), principal: Principal = Depends(principal_dependency)):
        filename = safe_component(file.filename or "documento")
        temp_dir = components.cfg.root / "workspace" / "Entrada"
        temp_dir.mkdir(parents=True, exist_ok=True)
        temp = temp_dir / ("rag_" + filename)
        try:
            max_bytes = int(components.cfg.section("documents").get("max_file_mb", 250)) * 1024 * 1024
            written = 0
            with temp.open("wb") as stream:
                while True:
                    block = await file.read(1024 * 1024)
                    if not block:
                        break
                    written += len(block)
                    if written > max_bytes:
                        raise HTTPException(status_code=413, detail=f"Archivo excede {components.cfg.section('documents').get('max_file_mb', 250)} MB")
                    stream.write(block)
            return components.documents.index(principal, temp, scope=scope, display_name=filename)
        finally:
            try:
                temp.unlink(missing_ok=True)
            except Exception:
                pass

    @router.get("/api/enterprise/documents")
    def list_documents(principal: Principal = Depends(principal_dependency)):
        docs = components.documents.list(principal)
        for item in docs:
            row = components.db.one("SELECT COUNT(*) AS n FROM document_chunks WHERE document_id=? AND active=1 AND version=?", (item["id"], item["current_version"]))
            item["chunk_count"] = int(row["n"] if row else 0)
        return {"documents": docs}

    @router.post("/api/enterprise/documents/{document_id}/reindex")
    def reindex_document(document_id: str, principal: Principal = Depends(principal_dependency)):
        try:
            return components.documents.reindex(principal, document_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.delete("/api/enterprise/documents/{document_id}")
    def delete_document(document_id: str, principal: Principal = Depends(principal_dependency)):
        try:
            components.documents.delete(principal, document_id)
            return {"ok": True}
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.get("/api/enterprise/datasets")
    def list_datasets(principal: Principal = Depends(principal_dependency)):
        return {"datasets": components.datasets.list(principal)}

    @router.get("/api/enterprise/settings")
    def settings(principal: Principal = Depends(principal_dependency)):
        return {
            "llm": components.cfg.section("llm"),
            "embeddings": components.cfg.section("embeddings"),
            "retrieval": components.cfg.section("retrieval"),
            "vector": {"backend_active": type(components.vectors).__name__, **components.cfg.section("vector")},
            "documents": components.cfg.section("documents"),
            "runtime": components.cfg.section("runtime"),
        }

    @router.put("/api/enterprise/settings")
    def update_settings(body: SettingsRequest, principal: Principal = Depends(admin_dependency)):
        cfg_path = components.cfg.root / "config" / "enterprise_ai.json"
        raw = json.loads(cfg_path.read_text(encoding="utf-8-sig")) if cfg_path.exists() else components.cfg.raw
        data = body.model_dump(exclude_none=True)
        if "llm_provider" in data:
            if data["llm_provider"] not in {"ollama", "lmstudio"}:
                raise HTTPException(status_code=400, detail="Proveedor no valido")
            raw.setdefault("llm", {})["provider"] = data["llm_provider"]
        if "ollama_model" in data:
            raw.setdefault("llm", {})["ollama_model"] = data["ollama_model"]
        if "lmstudio_model" in data:
            raw.setdefault("llm", {})["lmstudio_model"] = data["lmstudio_model"]
        if "embedding_provider" in data:
            if data["embedding_provider"] not in {"ollama", "lmstudio"}:
                raise HTTPException(status_code=400, detail="Proveedor de embeddings no valido")
            raw.setdefault("embeddings", {})["provider"] = data["embedding_provider"]
        if "embedding_model" in data:
            raw.setdefault("embeddings", {})["model"] = data["embedding_model"]
        if "embedding_lmstudio_model" in data:
            raw.setdefault("embeddings", {})["lmstudio_model"] = data["embedding_lmstudio_model"]
        if "generation_mode" in data:
            if data["generation_mode"] != "natural":
                raise HTTPException(status_code=400, detail="Modo de generación no válido")
            raw.setdefault("llm", {})["generation_mode"] = "natural"
            raw.setdefault("llm", {})["max_tokens"] = 0
        if "num_ctx" in data:
            raw.setdefault("llm", {})["num_ctx"] = max(2048, min(int(data["num_ctx"]), 32768))
        if "detailed_num_ctx" in data:
            raw.setdefault("llm", {})["detailed_num_ctx"] = max(4096, min(int(data["detailed_num_ctx"]), 65536))
        if "max_concurrent_generations" in data:
            raw.setdefault("runtime", {})["max_concurrent_generations"] = max(1, min(int(data["max_concurrent_generations"]), 8))
        if "queue_timeout_seconds" in data:
            raw.setdefault("runtime", {})["queue_timeout_seconds"] = max(5, min(int(data["queue_timeout_seconds"]), 600))
        for key in ("open_terminal_enabled", "warmup_llm"):
            if key in data:
                raw.setdefault("runtime", {})[key] = bool(data[key])
        for key in ("max_memories", "max_document_chunks", "max_context_chars"):
            if key in data:
                raw.setdefault("retrieval", {})[key] = int(data[key])
        cfg_path.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
        components.db.audit("settings.update", principal.company_id, principal.user_id, "settings", details={"fields": list(data)})
        return {"ok": True, "restart_required": True}

    @router.get("/api/enterprise/audit")
    def audit(limit: int = 100, principal: Principal = Depends(admin_dependency)):
        rows = components.db.query(
            "SELECT * FROM audit_events WHERE company_id=? ORDER BY id DESC LIMIT ?",
            (principal.company_id, max(1, min(limit, 500))),
        )
        return {"events": [dict(row) for row in rows]}

    app.include_router(router)
    return components
