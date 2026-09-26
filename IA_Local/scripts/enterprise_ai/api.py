from __future__ import annotations

import json
import shutil
import tempfile
import uuid
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from starlette.background import BackgroundTask
from pydantic import BaseModel, Field

from .factory import build_components
from .governed_sql_assistant import GovernedSqlAssistantBridge
from .observability import shutdown_logging
from .security import Principal, safe_component
from .admin_console import UNIFIED_ADMIN_HTML
from .product_ui import PRODUCT_HOME_HTML
from .product_assistant_ui import PRODUCT_ASSISTANT_HTML
from .product_workspaces_ui import PRODUCT_ANALYZE_HTML, PRODUCT_DATA_HTML, PRODUCT_REPORTS_HTML
from .product_settings_ui import PRODUCT_SETTINGS_HTML
from .providers import LMStudioProvider, OllamaProvider
from enterprise_control_plane import ControlPlaneError, EnterpriseControlPlane
from enterprise_identity import EnterpriseIdentityStore, IdentityError
from enterprise_tenant_registry import EnterpriseTenantRegistry, TenantRegistryError
from enterprise_onboarding import EnterpriseOnboarding
from enterprise_platform_config import EnterprisePlatformConfigStore, PlatformConfigError
from enterprise_sql_gateway import (
    EnterpriseSecretStore,
    EnterpriseSqlError,
    SqlServerPyodbcProvider,
    WindowsCredentialSecretProvider,
    discover_schema,
    public_sql_profile,
    test_connection,
    build_transient_sql_probe_profile,
    probe_sql_server_metadata,
)
from enterprise_backup_recovery import BackupError, backup as governed_backup, restore as governed_restore


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


class SemanticResolveRequest(BaseModel):
    columns: List[str] = Field(default_factory=list)
    inferred_roles: Dict[str, Optional[str]] = Field(default_factory=dict)
    on_date: Optional[str] = None


class RuleBindingRequest(BaseModel):
    rule_type: str
    target: str
    priority: int = 100
    scope: str = "company"


class FeedbackRequest(BaseModel):
    feedback_type: str
    target_type: Optional[str] = None
    target_ref: Optional[str] = None
    area: Optional[str] = None
    original_text: Optional[str] = None
    correction_text: Optional[str] = None
    proposal_type: str = "auto"
    proposal_name: Optional[str] = None
    physical_name: Optional[str] = None
    semantic_name: Optional[str] = None
    valid_from: Optional[str] = None
    valid_to: Optional[str] = None
    scope: str = "company"
    source_context: Dict[str, Any] = Field(default_factory=dict)


class FeedbackDecisionRequest(BaseModel):
    replace_conflicts: bool = False


class GovernanceValidateRequest(BaseModel):
    replace_conflicts: bool = False

class BusinessRuleCreateRequest(BaseModel):
    name: str
    expression: str
    area: Optional[str] = None
    description: Optional[str] = None
    scope: str = "company"
    valid_from: Optional[str] = None
    valid_to: Optional[str] = None

class SemanticDefinitionCreateRequest(BaseModel):
    physical_name: str
    semantic_name: str
    data_type: Optional[str] = None
    unit: Optional[str] = None
    area: Optional[str] = None
    description: Optional[str] = None
    scope: str = "company"
    valid_from: Optional[str] = None
    valid_to: Optional[str] = None

class AnalyticBindRequest(BaseModel):
    rule_type: str
    target: str
    priority: int = 100
    scope: str = "company"

class FineTuningBuildRequest(BaseModel):
    pass

class FineTuningDecisionRequest(BaseModel):
    approve: bool
    reason: Optional[str] = None

class FineTuningExportRequest(BaseModel):
    format: str = "jsonl"

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


class CompanyProfileRequest(BaseModel):
    display_name: str = Field(min_length=1, max_length=120)
    business_type: str = Field(min_length=1, max_length=40)
    accent_color: str = Field(min_length=7, max_length=7)
    theme: str = Field(min_length=1, max_length=40)


class EnterpriseUserCreateRequest(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    display_name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=12, max_length=256)
    role: str = Field(default="viewer", min_length=1, max_length=32)


class EnterpriseUserUpdateRequest(BaseModel):
    display_name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    role: Optional[str] = Field(default=None, min_length=1, max_length=32)


class EnterpriseUserStatusRequest(BaseModel):
    enabled: bool



class DataConnectionProbeRequest(BaseModel):
    server: str = Field(
        min_length=1,
        max_length=255,
    )
    database: str = Field(
        min_length=1,
        max_length=255,
    )
    authentication: str = Field(
        default="windows",
        min_length=1,
        max_length=32,
    )
    username: Optional[str] = Field(
        default=None,
        max_length=160,
    )
    password: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=256,
    )
    trust_server_certificate: bool = False




class DataConnectionCreateRequest(BaseModel):
    display_name: str = Field(min_length=1, max_length=120)
    server: str = Field(min_length=1, max_length=255)
    database: str = Field(min_length=1, max_length=255)
    authentication: str = Field(default="windows", min_length=1, max_length=32)
    username: Optional[str] = Field(default=None, max_length=160)
    password: Optional[str] = Field(default=None, min_length=1, max_length=256)
    trust_server_certificate: bool = False
    allowed_sources: List[str] = Field(min_length=1, max_length=200)


class DataConnectionUpdateRequest(BaseModel):
    display_name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    server: Optional[str] = Field(default=None, min_length=1, max_length=255)
    database: Optional[str] = Field(default=None, min_length=1, max_length=255)
    allowed_sources: Optional[List[str]] = Field(default=None, min_length=1, max_length=200)


class DataConnectionStatusRequest(BaseModel):
    enabled: bool


class AiConfigurationRequest(BaseModel):
    engine: str = Field(min_length=1, max_length=40)
    model: Optional[str] = Field(default=None, max_length=160)


class AppearanceRequest(BaseModel):
    theme: str = Field(min_length=1, max_length=40)
    accent_color: str = Field(min_length=7, max_length=7)


class RecoveryRequest(BaseModel):
    confirmed: bool = False


class AdvancedPreferencesRequest(BaseModel):
    locale: str = Field(min_length=2, max_length=32)
    timezone: str = Field(min_length=2, max_length=80)


class _CommercialAiAdapter:
    """Small bridge to existing local provider implementations.

    It deliberately owns neither configuration nor credentials; the platform
    configuration store remains the single authority for both.
    """

    def health(self, config: Dict[str, Any]) -> bool:
        provider = self._provider(config)
        if not provider.healthy():
            raise PlatformConfigError("AI_PROVIDER_UNAVAILABLE", "Motor local no disponible")
        return True

    def discover_models(self, config: Dict[str, Any]):
        if str(config.get("provider_type") or "").upper() != "OLLAMA":
            return {"supported": False}
        return self._provider(config).list_models()

    @staticmethod
    def _provider(config: Dict[str, Any]):
        kind = str(config.get("provider_type") or "").upper()
        model = str(config.get("model") or "discovery")
        timeout = int(config.get("timeout") or 30)
        if kind == "OLLAMA":
            return OllamaProvider(str(config.get("base_url") or ""), model, timeout=timeout)
        if kind == "OPENAI_COMPATIBLE_LOCAL":
            return LMStudioProvider(str(config.get("base_url") or ""), model, timeout=timeout)
        raise PlatformConfigError("AI_PROVIDER_INVALID", "Motor local inválido")


ASSISTANT_HTML = r"""
<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>IA Empresarial V8 - Asistente</title>
<style>body{margin:0;background:#f4f7fb;color:#142033;font-family:Segoe UI,Arial,sans-serif}.wrap{max-width:1100px;margin:28px auto;padding:0 18px}.card{background:#fff;border:1px solid #dbe3ee;border-radius:16px;box-shadow:0 10px 34px #2342a315;padding:22px}.head{display:flex;justify-content:space-between;gap:12px;align-items:center}.badge{background:#dbeafe;color:#1d4ed8;padding:5px 9px;border-radius:999px;font-size:12px}.workspace{border:1px solid #dbe3ee;border-radius:12px;padding:12px;margin:16px 0;background:#fbfdff}.source-list{font-size:12px;margin-top:6px}.msgs{height:52vh;overflow:auto;border:1px solid #dbe3ee;border-radius:12px;padding:14px;background:#fbfdff;margin:18px 0}.m{padding:11px 13px;border-radius:12px;margin:8px 0}.u{white-space:pre-wrap}.u{background:#e8f0ff;margin-left:16%}.a{background:#eefbf3;margin-right:10%}.src{font-size:12px;color:#506176;border-top:1px dashed #ccd5e0;margin-top:8px;padding-top:7px}.row{display:flex;gap:10px}.row textarea{flex:1;min-height:80px;padding:12px;border:1px solid #cbd5e1;border-radius:10px}.btn{border:0;background:#2563eb;color:white;border-radius:10px;padding:8px 12px;font-weight:700;cursor:pointer}.stop{background:#b91c1c;display:none}.status{font-size:12px;color:#64748b;margin-top:6px}.warn{background:#fff7ed;border:1px solid #fed7aa;border-radius:10px;padding:10px;margin:10px 0}.links a{margin-left:12px;color:#1d4ed8;text-decoration:none}.a p{margin:0 0 9px}.a p:last-child{margin-bottom:0}.a h3,.a h4{margin:10px 0 6px}.a ul,.a ol{margin:7px 0 7px 22px;padding:0}.a li{margin:3px 0}.a code{background:#e2e8f0;padding:1px 4px;border-radius:4px;font-family:Consolas,monospace}.a pre{background:#0f172a;color:#e2e8f0;padding:10px;border-radius:8px;overflow:auto;white-space:pre-wrap}</style></head>
<body><div class="wrap"><div class="card"><div class="head"><div><h2 style="margin:0">Asistente Empresarial Local <span class="badge">V8.5.5 Base Productiva + Streaming</span></h2><div style="color:#64748b">Memoria persistente, documentos fundamentados y cálculos determinísticos.</div></div><div class="links"><a href="/">Analizador</a><a id="admin" href="/admin">Administración</a><button id="logout" class="btn" style="display:none" onclick="enterpriseLogout()">Cerrar sesión</button></div></div><div id="auth" class="warn" style="display:none"></div><div id="workspace" class="workspace" style="display:none"><b>Fuentes del workspace</b><div class="status">Sube Excel/CSV o un documento compatible. Los datos estructurados se registran como dataset cuando el backend lo confirma.</div><div class="row"><input id="sourceFile" type="file" accept=".csv,.xlsx,.xls,.xlsm,.xlsb,.pdf,.docx,.txt,.md,.markdown"><button class="btn" id="uploadSource">Subir fuente</button></div><div id="sourceStatus" class="status"></div><div class="source-list"><b>Documentos</b><div id="documentList"></div><b>Datasets</b><div id="datasetList"></div><div class="row" style="margin-top:8px"><textarea id="analysisPrompt" placeholder="Ej. Genera un dashboard HTML, PDF y Excel con resumen ejecutivo."></textarea></div><div id="analysisStatus" class="status"></div></div><div class="source-list"><b>SQL Server</b> <button class="btn" id="refreshSqlSources" type="button" onclick="refreshSqlSources()">Actualizar</button><div class="status">Consulta únicamente conexiones, tablas y columnas autorizadas por la empresa. El navegador no construye ni envía SQL libre.</div><div class="row" style="margin-top:8px"><select id="sqlConnection" onchange="loadSqlSchema()" style="flex:1;padding:9px;border:1px solid #cbd5e1;border-radius:10px"></select><select id="sqlObject" onchange="renderSqlColumns()" style="flex:1;padding:9px;border:1px solid #cbd5e1;border-radius:10px"></select><input id="sqlLimit" type="number" min="1" max="500" value="50" title="Máximo de filas" style="width:90px;padding:9px;border:1px solid #cbd5e1;border-radius:10px"></div><div class="row" style="margin-top:8px"><select id="sqlColumns" multiple size="5" style="flex:1;padding:9px;border:1px solid #cbd5e1;border-radius:10px"></select><button class="btn" id="runSql" type="button" onclick="runSqlSelfService()">Consultar SQL</button></div><div id="sqlStatus" class="status"></div><div id="sqlResult" class="source-list"></div></div><div class="source-list"><b>Deliverables / Reportes</b> <button class="btn" id="refreshDeliverables">Actualizar</button><div id="deliverableStatus" class="status"></div><div id="deliverableList"></div></div></div><div id="msgs" class="msgs"></div><div class="row"><textarea id="q" placeholder="Pregunta sobre documentos, reglas del negocio o datasets..."></textarea><button class="btn" id="send">Enviar</button><button class="btn stop" id="stop">Detener</button></div></div></div>
<script>
let token=sessionStorage.getItem('iaEnterpriseSession')||'',currentUser=null;document.getElementById('admin').href='/admin';
function clearEnterpriseSession(){token='';currentUser=null;sessionStorage.removeItem('iaEnterpriseSession');if(activeController){activeController.abort();activeController=null}document.getElementById('logout').style.display='none';document.getElementById('workspace').style.display='none';document.getElementById('deliverableList').replaceChildren();document.getElementById('deliverableStatus').textContent='';resetSqlWorkspace();document.getElementById('q').disabled=true;document.getElementById('send').disabled=true}
function showLogin(message=''){clearEnterpriseSession();document.getElementById('auth').style.display='block';document.getElementById('auth').innerHTML='<h3>Acceso empresarial</h3><input id="authUser" autocomplete="username" placeholder="Usuario"><input id="authPassword" type="password" autocomplete="current-password" placeholder="Contraseña"><button class="btn" onclick="enterpriseLogin()">Iniciar sesión</button><div class="status">'+escHtml(message)+'</div>'}
function handleUnauthorized(){showLogin('Tu sesión no es válida.')}
async function protectedFetch(url,options={}){const headers={...(options.headers||{}),'Authorization':'Bearer '+token};const response=await fetch(url,{...options,headers});if(response.status===401){handleUnauthorized();return null}return response}
function sourceMessage(message){document.getElementById('sourceStatus').textContent=message}
function renderSources(documents,datasets){const docs=document.getElementById('documentList'),sets=document.getElementById('datasetList');docs.replaceChildren();sets.replaceChildren();for(const item of documents){const row=document.createElement('div');row.textContent='DOCUMENT · '+item.name+' · '+(item.status||'N/D')+' · '+(item.extension||'');docs.appendChild(row)}if(!documents.length)docs.textContent='Sin documentos.';for(const item of datasets){const row=document.createElement('div'),label=document.createElement('span'),button=document.createElement('button');label.textContent='DATASET · '+item.name+' · '+((item.columns||[]).length)+' columnas';button.className='btn';button.style.marginLeft='8px';button.textContent='Generar reporte';button.onclick=()=>generateDatasetReport(item.id,item.name,button);row.append(label,button);sets.appendChild(row)}if(!datasets.length)sets.textContent='Sin datasets registrados.'}
async function refreshSources(){sourceMessage('Actualizando fuentes...');const [docs,sets]=await Promise.all([protectedFetch('/api/enterprise/documents'),protectedFetch('/api/enterprise/datasets')]);if(!docs||!sets)return;if(docs.status===403||sets.status===403){sourceMessage('Acceso denegado para consultar fuentes.');return}if(!docs.ok||!sets.ok){sourceMessage('No se pudo actualizar el workspace.');return}const [docData,setData]=await Promise.all([docs.json(),sets.json()]);renderSources(docData.documents||[],setData.datasets||[]);sourceMessage('Fuentes listas.')}
function analysisMessage(message){document.getElementById('analysisStatus').textContent=message}
async function generateDatasetReport(datasetId,datasetName,button){const promptValue=document.getElementById('analysisPrompt').value.trim();if(!datasetId){analysisMessage('Dataset no disponible.');return}if(!promptValue){analysisMessage('Escribe qué reporte o análisis deseas generar.');return}button.disabled=true;analysisMessage('Generando resultado empresarial para '+String(datasetName||'dataset')+'...');try{const response=await protectedFetch('/api/enterprise/datasets/'+encodeURIComponent(datasetId)+'/analyze',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({prompt:promptValue})});if(!response)return;if(response.status===403){analysisMessage('Acceso denegado para ejecutar análisis.');return}if(response.status===404){analysisMessage('El dataset no está disponible.');return}if(!response.ok){analysisMessage('No se pudo generar el resultado empresarial.');return}const payload=await response.json();analysisMessage(payload.deliverable_run?'Resultado generado y registrado.':'Análisis completado.');await refreshDeliverables()}catch(e){analysisMessage('No se pudo ejecutar el análisis local.')}finally{button.disabled=false}}
let SQL_OBJECTS=[];
function sqlTenantSuffix(prefix){if(!currentUser||!(currentUser.roles||[]).includes('SYSTEM_ADMIN'))return '';const tenant=String(currentUser.tenant_id||'').trim();return tenant?String(prefix||'?')+'tenant_id='+encodeURIComponent(tenant):''}
function sqlMessage(text){document.getElementById('sqlStatus').textContent=String(text||'')}
function resetSqlWorkspace(){SQL_OBJECTS=[];for(const id of ['sqlConnection','sqlObject','sqlColumns']){const el=document.getElementById(id);if(el)el.replaceChildren()}const result=document.getElementById('sqlResult');if(result)result.replaceChildren();sqlMessage('')}
function renderSqlConnections(items){const select=document.getElementById('sqlConnection');select.replaceChildren();const eligible=(items||[]).filter(item=>item&&item.enabled!==false&&item.read_only!==false);for(const item of eligible){const option=document.createElement('option');option.value=String(item.connection_id||'');option.textContent=String(item.database||item.connection_id||'SQL')+' · '+String(item.server||'servidor');select.appendChild(option)}if(!eligible.length){const option=document.createElement('option');option.value='';option.textContent='Sin conexiones SQL disponibles';select.appendChild(option)}}
function renderSqlObjects(){const select=document.getElementById('sqlObject');select.replaceChildren();for(let index=0;index<SQL_OBJECTS.length;index++){const item=SQL_OBJECTS[index]||{};const option=document.createElement('option');option.value=String(index);option.textContent=String(item.schema||'')+'.'+String(item.name||'');select.appendChild(option)}if(!SQL_OBJECTS.length){const option=document.createElement('option');option.value='';option.textContent='Sin tablas autorizadas';select.appendChild(option)}renderSqlColumns()}
function renderSqlColumns(){const columns=document.getElementById('sqlColumns');columns.replaceChildren();const index=Number(document.getElementById('sqlObject').value);const object=Number.isInteger(index)?SQL_OBJECTS[index]:null;for(const item of ((object&&object.columns)||[])){const option=document.createElement('option');option.value=String(item.name||'');option.textContent=String(item.name||'')+(item.type?' · '+String(item.type):'');columns.appendChild(option)}}
async function refreshSqlSources(){sqlMessage('Actualizando fuentes SQL...');const response=await protectedFetch('/api/sql/connections'+sqlTenantSuffix('?'));if(!response)return;if(response.status===403){resetSqlWorkspace();sqlMessage('Tu rol no tiene permiso para consultar SQL Server.');return}if(!response.ok){resetSqlWorkspace();sqlMessage('No se pudieron consultar las fuentes SQL.');return}const payload=await response.json();renderSqlConnections(payload.items||[]);if(document.getElementById('sqlConnection').value){await loadSqlSchema()}else{SQL_OBJECTS=[];renderSqlObjects();sqlMessage('No hay conexiones SQL habilitadas para tu empresa.')}}
async function loadSqlSchema(){const connectionId=document.getElementById('sqlConnection').value;SQL_OBJECTS=[];renderSqlObjects();if(!connectionId){sqlMessage('Selecciona una conexión SQL.');return}sqlMessage('Consultando esquema autorizado...');const response=await protectedFetch('/api/sql/schema?connection_id='+encodeURIComponent(connectionId)+sqlTenantSuffix('&'));if(!response)return;if(response.status===403){sqlMessage('Acceso SQL denegado.');return}if(response.status===404){sqlMessage('La conexión SQL ya no está disponible.');return}if(!response.ok){sqlMessage('No se pudo consultar el esquema SQL.');return}const payload=await response.json();SQL_OBJECTS=Array.isArray(payload.objects)?payload.objects:[];renderSqlObjects();sqlMessage(SQL_OBJECTS.length?'Esquema SQL listo.':'La conexión no tiene tablas autorizadas.')}

function renderSqlResult(payload){const host=document.getElementById('sqlResult');host.replaceChildren();const columns=Array.isArray(payload.columns)?payload.columns:[];const rows=Array.isArray(payload.rows)?payload.rows:[];if(!columns.length){host.textContent='La consulta no devolvió columnas.';return}const meta=document.createElement('div');meta.className='status';meta.textContent=String(payload.row_count||0)+' filas'+(payload.truncated?' · resultado truncado':'');host.appendChild(meta);const wrap=document.createElement('div');wrap.style.overflow='auto';const table=document.createElement('table');table.style.borderCollapse='collapse';table.style.width='100%';const thead=document.createElement('thead'),tr=document.createElement('tr');for(const column of columns){const th=document.createElement('th');th.textContent=String(column);th.style.textAlign='left';th.style.padding='6px';th.style.borderBottom='1px solid #cbd5e1';tr.appendChild(th)}thead.appendChild(tr);table.appendChild(thead);const tbody=document.createElement('tbody');for(const row of rows){const trRow=document.createElement('tr');for(const value of (Array.isArray(row)?row:[])){const td=document.createElement('td');td.textContent=value===null?'NULL':String(value);td.style.padding='6px';td.style.borderBottom='1px solid #e2e8f0';trRow.appendChild(td)}tbody.appendChild(trRow)}table.appendChild(tbody);wrap.appendChild(table);host.appendChild(wrap)}
async function runSqlSelfService(){const connectionId=document.getElementById('sqlConnection').value,index=Number(document.getElementById('sqlObject').value),object=Number.isInteger(index)?SQL_OBJECTS[index]:null,columns=Array.from(document.getElementById('sqlColumns').selectedOptions).map(option=>option.value).filter(Boolean),limit=Number(document.getElementById('sqlLimit').value),button=document.getElementById('runSql');if(!connectionId){sqlMessage('Selecciona una conexión SQL.');return}if(!object||!object.schema||!object.name){sqlMessage('Selecciona una tabla autorizada.');return}if(!columns.length){sqlMessage('Selecciona al menos una columna.');return}if(!Number.isInteger(limit)||limit<1||limit>500){sqlMessage('El límite debe estar entre 1 y 500 filas.');return}button.disabled=true;sqlMessage('Ejecutando consulta gobernada...');document.getElementById('sqlResult').replaceChildren();try{const response=await protectedFetch('/api/sql/query-safe'+sqlTenantSuffix('?'),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({connection_id:connectionId,schema:String(object.schema),object:String(object.name),columns:columns,limit:limit})});if(!response)return;let payload={};try{payload=await response.json()}catch{}if(response.status===403){sqlMessage('Acceso SQL denegado.');return}if(response.status===404){sqlMessage('La conexión SQL no está disponible.');return}if(!response.ok){const detail=payload.detail||{};sqlMessage(typeof detail==='object'?(detail.message||detail.code||'Consulta SQL rechazada.'):'Consulta SQL rechazada.');return}renderSqlResult(payload);sqlMessage('Consulta SQL completada de forma gobernada.')}catch(e){sqlMessage('No se pudo ejecutar la consulta SQL local.')}finally{button.disabled=false}}

async function uploadSource(){const input=document.getElementById('sourceFile'),button=document.getElementById('uploadSource'),file=input.files[0];if(!file){sourceMessage('Selecciona un archivo compatible.');return}button.disabled=true;sourceMessage('Subiendo fuente...');try{const data=new FormData();data.append('file',file);data.append('scope','company');const response=await protectedFetch('/api/enterprise/documents',{method:'POST',body:data});if(!response)return;if(response.status===403){sourceMessage('Acceso denegado para subir fuentes.');return}let payload={};try{payload=await response.json()}catch{}if(!response.ok){sourceMessage(payload.detail||'No se pudo registrar la fuente.');return}input.value='';sourceMessage('Fuente registrada: '+(payload.name||file.name)+'.');await refreshSources()}catch(e){sourceMessage('No se pudo conectar con el servidor local.')}finally{button.disabled=false}}
function deliverableMessage(message){document.getElementById('deliverableStatus').textContent=message}
function safeDownloadName(value,fallback){const name=String(value||'').replace(/[^A-Za-z0-9._-]/g,'_').slice(0,160);return name||fallback}
function renderDeliverables(records){const list=document.getElementById('deliverableList');list.replaceChildren();for(const record of records){const row=document.createElement('div'),title=document.createElement('div'),meta=document.createElement('div'),formats=document.createElement('div');title.textContent='REPORTE · '+String(record.run_id||'N/D');meta.className='status';meta.textContent=(record.status||'N/D')+' · '+(record.created_at||'');row.append(title,meta);for(const item of (record.deliverables||[])){if(!item||!item.format)continue;const button=document.createElement('button');button.className='btn';button.textContent=String(item.format).toUpperCase();button.onclick=()=>downloadDeliverable(record.run_id,item.format,item.filename,button);formats.appendChild(button)}row.appendChild(formats);list.appendChild(row)}if(!records.length)list.textContent='Aún no hay reportes disponibles.'}
async function refreshDeliverables(){deliverableMessage('Actualizando reportes...');const response=await protectedFetch('/api/deliverables');if(!response)return;if(response.status===403){deliverableMessage('Acceso denegado para consultar reportes.');return}if(!response.ok){deliverableMessage('No se pudieron consultar los reportes.');return}const payload=await response.json();renderDeliverables(Array.isArray(payload.items)?payload.items:[]);deliverableMessage('Reportes listos.')}
async function downloadDeliverable(runId,kind,filename,button){if(!runId||!kind)return;button.disabled=true;deliverableMessage('Descargando reporte...');try{const response=await protectedFetch('/api/deliverables/'+encodeURIComponent(runId)+'/download/'+encodeURIComponent(kind));if(!response)return;if(response.status===403){deliverableMessage('Acceso denegado para descargar el reporte.');return}if(!response.ok){deliverableMessage('El reporte no está disponible.');return}const blob=await response.blob();if(!blob.size){deliverableMessage('El reporte no está disponible.');return}const url=URL.createObjectURL(blob),link=document.createElement('a');link.href=url;link.download=safeDownloadName(filename,String(runId)+'.'+String(kind));link.click();setTimeout(()=>URL.revokeObjectURL(url),0);deliverableMessage('Descarga iniciada.')}catch(e){deliverableMessage('No se pudo descargar el reporte.')}finally{button.disabled=false}}
async function establishSession(){if(!token){showLogin();return false}try{const r=await protectedFetch('/api/auth/me');if(!r)return false;if(r.status===403){document.getElementById('auth').style.display='block';document.getElementById('auth').textContent='Acceso denegado.';return false}if(!r.ok)throw new Error('Servicio no disponible');currentUser=await r.json();document.getElementById('auth').style.display='none';document.getElementById('logout').style.display='';document.getElementById('workspace').style.display='block';document.getElementById('q').disabled=false;document.getElementById('send').disabled=false;await Promise.all([refreshSources(),refreshDeliverables(),refreshSqlSources()]);return true}catch(e){document.getElementById('auth').style.display='block';document.getElementById('auth').textContent='No se pudo validar la sesión con el servidor local.';return false}}
async function enterpriseLogin(){const u=document.getElementById('authUser').value,p=document.getElementById('authPassword');try{const r=await fetch('/api/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:u,password:p.value})});let d={};try{d=await r.json()}catch{}if(!r.ok){showLogin('Credenciales inválidas o acceso no disponible.');return}token=d.token;sessionStorage.setItem('iaEnterpriseSession',token);p.value='';await establishSession()}catch(e){showLogin('No se pudo conectar con el servidor local.')}finally{if(p)p.value=''}}
async function enterpriseLogout(){try{if(token)await protectedFetch('/api/auth/logout',{method:'POST'})}finally{showLogin('Sesión cerrada.')}}
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
function feedbackButtons(doneEvent,answer){const box=document.createElement('div');box.className='status';box.style.marginTop='8px';const ok=document.createElement('button');ok.className='btn ok';ok.textContent='👍 Correcto';ok.style.padding='5px 9px';const bad=document.createElement('button');bad.className='btn danger';bad.textContent='👎 Requiere corrección';bad.style.padding='5px 9px';box.append(ok,bad);const forbidden=()=>{box.textContent='Acceso denegado.'};ok.onclick=async()=>{ok.disabled=bad.disabled=true;const r=await protectedFetch('/api/enterprise/feedback',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({feedback_type:'CORRECTO',target_type:'chat',target_ref:doneEvent.request_id||null,original_text:answer,source_context:{sources:doneEvent.sources||[]}})});if(!r)return;if(r.status===403){forbidden();return}box.textContent=r.ok?'Feedback registrado.':'No se pudo registrar el feedback.'};bad.onclick=async()=>{const correction=prompt('Indica la corrección. Se guardará como PROPUESTA, no como verdad validada:');if(!correction)return;const r=await protectedFetch('/api/enterprise/feedback',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({feedback_type:'REQUIERE_CORRECCION',target_type:'chat',target_ref:doneEvent.request_id||null,original_text:answer,correction_text:correction,proposal_type:'auto',source_context:{sources:doneEvent.sources||[]}})});if(!r)return;if(r.status===403){forbidden();return}let d={};try{d=await r.json()}catch{}if(!r.ok){alert(d.detail||'No se pudo registrar la corrección');return}box.innerHTML='Corrección registrada como <b>'+escHtml(d.proposal_type||'propuesta')+'</b> / '+escHtml(d.proposal_status||'PROPUESTO')+'. ';if(d.proposal_object_id){const save=document.createElement('button');save.className='btn ok';save.textContent='Guardar / Validar';save.style.padding='5px 9px';const reject=document.createElement('button');reject.className='btn danger';reject.textContent='Rechazar';reject.style.padding='5px 9px';box.append(save,reject);save.onclick=async()=>{const vr=await protectedFetch('/api/enterprise/feedback/'+encodeURIComponent(d.id)+'/validate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({replace_conflicts:false})});if(!vr)return;if(vr.status===403){forbidden();return}let vd={};try{vd=await vr.json()}catch{}if(vr.ok)box.textContent='Propuesta VALIDADA y guardada.';else alert(vd.detail||'No se pudo validar; puede existir un conflicto.')};reject.onclick=async()=>{const rr=await protectedFetch('/api/enterprise/feedback/'+encodeURIComponent(d.id)+'/reject',{method:'POST'});if(!rr)return;if(rr.status===403){forbidden();return}if(rr.ok)box.textContent='Propuesta rechazada.'}}};return box}
function sourceHtml(d){let src=(d.sources||[]).map(x=>{if(x.type==='dataset')return 'Dataset: '+escHtml(x.file)+' | '+escHtml(x.sheet||'')+' | filas usadas: '+escHtml(x.rows_used??'N/D');if(x.type==='memory')return 'Memoria: '+escHtml(x.category)+' | '+escHtml(x.source_type||'fuente local');if(x.type==='model_knowledge')return 'Conocimiento general: '+escHtml(x.provider||'modelo local')+' / '+escHtml(x.model||'N/D');if(x.type==='system_capabilities')return 'Capacidades del sistema: configuración local verificada | '+escHtml(x.model||'N/D');return 'Documento: '+escHtml(x.file)+(x.page?' | pág. '+escHtml(x.page):'')+(x.sheet?' | hoja '+escHtml(x.sheet):'')+(x.rows?' | filas '+escHtml(x.rows):'')}).join('<br>');if(d.retrieval&&d.retrieval.response_profile){src+=(src?'<br>':'')+'Respuesta: '+escHtml(d.retrieval.response_profile);const cr=d.retrieval.completion_reason||'natural';if(cr==='natural')src+=' | finalización natural';else if(cr==='complete')src+=' | información del sistema completa';else if(cr==='continued_to_eos')src+=' | continuada automáticamente hasta completar';else if(cr==='repetition_guard_stop')src+=' | continuación detenida por repetición';else if(cr==='technical_context_stop')src+=' | límite técnico de contexto alcanzado';else if(cr==='operational_safety_stop')src+=' | detenida por salvaguarda operativa';if((d.retrieval.continuations||0)>0)src+=' | continuaciones: '+escHtml(d.retrieval.continuations);const cp=d.retrieval.context_plan;if(cp&&cp.num_ctx)src+=' | contexto dinámico: '+escHtml(cp.num_ctx);}if(d.timings_ms){if(d.timings_ms.first_token_ms!=null&&d.timings_ms.first_token_ms>0)src+=(src?'<br>':'')+'Primer token: '+escHtml(d.timings_ms.first_token_ms)+' ms';if(d.timings_ms.queue_ms!=null&&d.timings_ms.queue_ms>0)src+=(src?'<br>':'')+'Cola: '+escHtml(d.timings_ms.queue_ms)+' ms';src+=(src?'<br>':'')+'Tiempo total: '+escHtml(d.timings_ms.total_ms??'N/D')+' ms'}if(d.request_id)src+=(src?'<br>':'')+'Solicitud: '+escHtml(d.request_id);if(d.trace_id)src+=(src?'<br>':'')+'Trazabilidad: <a href="/api/enterprise/traces/'+encodeURIComponent(d.trace_id)+'/explain" target="_blank">¿Cómo obtuve este resultado?</a>';return src}
async function send(){const q=document.getElementById('q');const m=q.value.trim();if(!m||!token||activeController)return;add('u',m);q.value='';const btn=document.getElementById('send'),stop=document.getElementById('stop');btn.disabled=true;stop.style.display='block';activeController=new AbortController();const bubble=add('a','Preparando respuesta...');let answer='',done=false;const t0=Date.now();const setStatus=t=>{if(!answer){bubble.textContent=t}else{let st=bubble.querySelector('.stream-status');if(!st){st=document.createElement('div');st.className='status stream-status';bubble.appendChild(st)}st.textContent=t}};try{const r=await protectedFetch('/api/enterprise/chat/stream',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:m,history:hist.slice(-6)}),signal:activeController.signal});if(!r)return;if(r.status===403){bubble.textContent='Acceso denegado.';return}if(!r.ok){let d={};try{d=await r.json()}catch{}throw new Error(d.detail||d.error||'Error '+r.status)}const reader=r.body.getReader(),dec=new TextDecoder();let buf='';while(true){const x=await reader.read();if(x.done)break;buf+=dec.decode(x.value,{stream:true});let lines=buf.split('\n');buf=lines.pop();for(const line of lines){if(!line.trim())continue;const ev=JSON.parse(line);if(ev.type==='status'){setStatus(ev.message+' '+Math.floor((Date.now()-t0)/1000)+' s');continue}if(ev.type==='first_token'){setStatus('Generando... primer token en '+ev.first_token_ms+' ms');continue}if(ev.type==='token'){answer+=ev.text;bubble.innerHTML=md(answer);msgs.scrollTop=msgs.scrollHeight;continue}if(ev.type==='error'){throw new Error(ev.message||'No se pudo generar la respuesta')}if(ev.type==='done'){done=true;answer=ev.answer||answer;bubble.innerHTML=md(answer);const src=document.createElement('div');src.className='src';src.innerHTML=sourceHtml(ev);bubble.appendChild(src);bubble.appendChild(feedbackButtons(ev,answer));hist.push({role:'user',content:m},{role:'assistant',content:answer});msgs.scrollTop=msgs.scrollHeight;continue}}}if(!done&&answer){const src=document.createElement('div');src.className='src';src.textContent='Respuesta parcial.';bubble.appendChild(src)}}catch(e){if(e.name==='AbortError'){if(answer){bubble.innerHTML=md(answer);const src=document.createElement('div');src.className='src';src.textContent='Generación detenida por el usuario.';bubble.appendChild(src)}else bubble.textContent='Generación detenida por el usuario.'}else{bubble.textContent='ERROR: '+e.message}}finally{activeController=null;btn.disabled=false;stop.style.display='none'}}
function stopGeneration(){if(activeController)activeController.abort()}
async function confirmMem(id){const r=await protectedFetch('/api/enterprise/memories/'+id+'/confirm',{method:'POST'});if(!r)return;if(r.status===403){alert('Acceso denegado.');return}alert(r.ok?'Memoria confirmada':'No se pudo confirmar')}
document.getElementById('send').onclick=send;document.getElementById('stop').onclick=stopGeneration;document.getElementById('uploadSource').onclick=uploadSource;document.getElementById('refreshDeliverables').onclick=refreshDeliverables;document.getElementById('q').addEventListener('keydown',e=>{if(e.ctrlKey&&e.key==='Enter')send()});if(token){establishSession()}else{showLogin()}
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
let token=sessionStorage.getItem('iaEnterpriseSession')||'';if(!token)document.getElementById('auth').style.display='block';document.getElementById('assistant').href='/assistant';const H={'Authorization':'Bearer '+token};let MEM=[];
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

    def _close_enterprise_components() -> None:
        closer = getattr(
            components.vectors,
            "close",
            None,
        )

        if callable(closer):
            closer()

        shutdown_logging()

    app.router.add_event_handler(
        "shutdown",
        _close_enterprise_components,
    )

    def _build_commercial_stores(current_components):
        current_root = Path(current_components.cfg.root)

        current_control_plane = EnterpriseControlPlane(
            current_components.cfg.root
        )

        current_tenants = EnterpriseTenantRegistry(
            current_root
            / "workspace"
            / "Reportes"
            / ".tenants"
        )

        current_identity = EnterpriseIdentityStore(
            current_root
            / "workspace"
            / "Reportes"
            / ".identity",
            current_tenants,
        )

        current_platform = EnterprisePlatformConfigStore(
            current_root
            / "workspace"
            / "Reportes"
            / ".platform_config",
            current_tenants,
        )

        current_onboarding = EnterpriseOnboarding(
            current_root
            / "workspace"
            / "Reportes"
        )

        return (
            current_control_plane,
            current_tenants,
            current_identity,
            current_platform,
            current_onboarding,
        )

    (
        control_plane,
        enterprise_tenants,
        enterprise_identity,
        enterprise_platform,
        enterprise_onboarding,
    ) = _build_commercial_stores(components)

    def _reload_enterprise_components() -> None:
        nonlocal components
        nonlocal control_plane
        nonlocal enterprise_tenants
        nonlocal enterprise_identity
        nonlocal enterprise_platform
        nonlocal enterprise_onboarding

        components = build_components(root)

        (
            control_plane,
            enterprise_tenants,
            enterprise_identity,
            enterprise_platform,
            enterprise_onboarding,
        ) = _build_commercial_stores(components)

    router = APIRouter()

    def principal_dependency(authorization: Optional[str] = Header(default=None)) -> Principal:
        raw = None
        if authorization and authorization.lower().startswith("bearer "):
            raw = authorization.split(" ", 1)[1].strip()
        if not raw:
            raise HTTPException(status_code=401, detail="Token requerido")
        try:
            user = enterprise_identity.authenticate(raw)
            return Principal(user["tenant_id"], user["user_id"], "admin" if "SYSTEM_ADMIN" in user["roles"] else "user")
        except (IdentityError, TenantRegistryError) as exc:
            raise HTTPException(status_code=401, detail="Sesión empresarial inválida") from exc

    def admin_dependency(principal: Principal = Depends(principal_dependency)) -> Principal:
        try:
            user = enterprise_identity.get(principal.user_id)
        except IdentityError as exc:
            raise HTTPException(status_code=401, detail="Sesión empresarial inválida") from exc
        if user["tenant_id"] != principal.company_id or not enterprise_identity.has_permission(user, "admin:audit"):
            raise HTTPException(status_code=403, detail="Permiso administrativo requerido")
        return principal

    def require_permission(permission: str):
        def dependency(principal: Principal = Depends(principal_dependency)) -> Principal:
            try:
                user = enterprise_identity.get(principal.user_id)
            except IdentityError as exc:
                raise HTTPException(status_code=401, detail="Sesión empresarial inválida") from exc
            if user["tenant_id"] != principal.company_id or not enterprise_identity.has_permission(user, permission):
                raise HTTPException(status_code=403, detail="Permiso empresarial insuficiente")
            return principal
        return dependency

    def control_plane_response(call):
        try:
            return call()
        except ControlPlaneError as exc:
            status = 401 if exc.code == "CONTROL_PLANE_AUTH_REQUIRED" else (503 if exc.code.startswith("CONTROL_PLANE_RELEASE_METADATA") else 403)
            raise HTTPException(status_code=status, detail=exc.code) from exc

    @router.get("/assistant", response_class=HTMLResponse)
    def assistant_page():
        return PRODUCT_ASSISTANT_HTML

    @router.get(
        "/assistant/legacy",
        response_class=HTMLResponse,
        include_in_schema=False,
    )
    def legacy_assistant_page():
        return ASSISTANT_HTML

    @router.get("/admin", response_class=HTMLResponse)
    def admin_page():
        return UNIFIED_ADMIN_HTML

    @router.get("/app", response_class=HTMLResponse, include_in_schema=False)
    def product_home_page():
        return PRODUCT_HOME_HTML


    @router.get("/analyze", include_in_schema=False)
    def product_analyze_page():
        return HTMLResponse(PRODUCT_ANALYZE_HTML)
    @router.get("/data", include_in_schema=False)
    def product_data_page():
        return HTMLResponse(PRODUCT_DATA_HTML)
    @router.get("/reports", include_in_schema=False)
    def product_reports_page():
        return HTMLResponse(PRODUCT_REPORTS_HTML)
    @router.get("/settings", include_in_schema=False)
    def product_settings_page():
        return HTMLResponse(PRODUCT_SETTINGS_HTML)

    def company_profile_payload(principal: Principal) -> Dict[str, Any]:
        public = enterprise_platform.public_effective_config(principal.company_id)
        return {
            "display_name": public.get("display_name") or "IA Empresarial Local",
            "business_type": public.get("business_type") or "Otro",
            "accent_color": public.get("accent_color") or "#1d67d2",
            "theme": public.get("theme") or "professional-light",
            "logo_configured": bool(public.get("logo_reference")),
        }

    @router.get("/api/enterprise/company-profile")
    def company_profile(principal: Principal = Depends(require_permission("config:read"))):
        try:
            user = enterprise_identity.get(principal.user_id)
            return {
                "company": company_profile_payload(principal),
                "can_edit": enterprise_identity.has_permission(user, "config:write"),
            }
        except (IdentityError, TenantRegistryError, PlatformConfigError) as exc:
            raise HTTPException(status_code=401, detail="Configuración empresarial no disponible") from exc

    @router.put("/api/enterprise/company-profile")
    def update_company_profile(
        body: CompanyProfileRequest,
        principal: Principal = Depends(require_permission("config:write")),
    ):
        display_name = body.display_name.strip()
        if not display_name or any(ord(char) < 32 for char in display_name):
            raise HTTPException(status_code=400, detail="El nombre de la empresa no es válido")
        try:
            current = enterprise_platform.tenant_config(principal.company_id)
            branding = dict(current.get("branding") or {})
            branding.update({
                "display_name": display_name,
                "accent_color": body.accent_color,
                "theme": body.theme,
            })
            enterprise_platform.update_tenant(principal.company_id, {
                "display_name": display_name,
                "business_type": body.business_type,
                "theme": body.theme,
                "branding": branding,
            })
            components.db.audit(
                "company.profile.updated",
                principal.company_id,
                principal.user_id,
                "company_profile",
                details={"fields": ["display_name", "business_type", "accent_color", "theme"]},
            )
            return {"ok": True, "company": company_profile_payload(principal)}
        except (TenantRegistryError, PlatformConfigError) as exc:
            raise HTTPException(status_code=400, detail="Los cambios de la empresa no son válidos") from exc


    _COMMERCIAL_USER_ROLES = {
        "administrator": "TENANT_ADMIN",
        "analyst": "ANALYST",
        "viewer": "VIEWER",
    }

    def enterprise_user_actor(principal: Principal) -> Dict[str, Any]:
        try:
            actor = enterprise_identity.get(principal.user_id)
        except IdentityError as exc:
            raise HTTPException(status_code=401, detail="Sesión empresarial inválida") from exc
        if actor.get("tenant_id") != principal.company_id:
            raise HTTPException(status_code=403, detail="Acceso empresarial no permitido")
        return actor

    def enterprise_user_target(principal: Principal, username: str) -> Dict[str, Any]:
        wanted = str(username or "").strip().lower()
        for item in enterprise_identity.list(principal.company_id):
            if str(item.get("username") or "").lower() == wanted:
                return item
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    def enterprise_user_role(item: Dict[str, Any]) -> tuple[str, str, bool]:
        roles = set(item.get("roles") or [])
        if "SYSTEM_ADMIN" in roles:
            return "administrator", "Administrador", False
        if roles == {"TENANT_ADMIN"}:
            return "administrator", "Administrador", True
        if roles == {"ANALYST"}:
            return "analyst", "Analista", True
        if roles == {"VIEWER"}:
            return "viewer", "Consulta", True
        return "custom", "Acceso personalizado", False

    def enterprise_user_public(item: Dict[str, Any], principal: Principal) -> Dict[str, Any]:
        role_key, role_label, role_editable = enterprise_user_role(item)
        enabled = item.get("status") == "ACTIVE"
        protected = "SYSTEM_ADMIN" in set(item.get("roles") or [])
        current = item.get("user_id") == principal.user_id
        return {
            "username": item.get("username") or "",
            "display_name": item.get("display_name") or item.get("username") or "",
            "role": role_key,
            "role_label": role_label,
            "enabled": enabled,
            "status_label": "Activo" if enabled else "Desactivado",
            "is_current": current,
            "role_editable": bool(role_editable and not current and not protected),
            "status_editable": bool(not current and not protected),
        }

    def enterprise_user_capabilities(principal: Principal) -> Dict[str, bool]:
        actor = enterprise_user_actor(principal)
        return {
            "can_create": enterprise_identity.has_permission(actor, "user:create"),
            "can_update": enterprise_identity.has_permission(actor, "user:update"),
            "can_disable": enterprise_identity.has_permission(actor, "user:disable"),
            "can_assign_role": enterprise_identity.has_permission(actor, "user:role_assign"),
        }

    def enterprise_user_identity_error(exc: IdentityError) -> None:
        status = {
            "USER_NOT_FOUND": 404,
            "USER_ALREADY_EXISTS": 409,
            "LAST_SYSTEM_ADMIN": 409,
            "ROLE_INVALID": 400,
            "USER_INVALID_ID": 400,
            "PASSWORD_INVALID": 400,
        }.get(exc.code, 400)
        message = {
            "USER_NOT_FOUND": "Usuario no encontrado",
            "USER_ALREADY_EXISTS": "Ya existe un usuario con ese acceso",
            "LAST_SYSTEM_ADMIN": "Debe permanecer al menos un administrador activo",
            "ROLE_INVALID": "El rol seleccionado no es válido",
            "USER_INVALID_ID": "El nombre de acceso no es válido",
            "PASSWORD_INVALID": "La contraseña temporal debe tener al menos 12 caracteres",
        }.get(exc.code, "No se pudo completar la operación de usuarios")
        raise HTTPException(status_code=status, detail=message) from exc

    def enterprise_other_active_admin_exists(principal: Principal, target: Dict[str, Any]) -> bool:
        for item in enterprise_identity.list(principal.company_id):
            if item.get("user_id") == target.get("user_id"):
                continue
            if item.get("status") != "ACTIVE":
                continue
            roles = set(item.get("roles") or [])
            if roles.intersection({"SYSTEM_ADMIN", "TENANT_ADMIN"}):
                return True
        return False

    @router.get("/api/enterprise/users")
    def enterprise_users(principal: Principal = Depends(require_permission("user:list"))):
        users = [
            enterprise_user_public(item, principal)
            for item in enterprise_identity.list(principal.company_id)
        ]
        users.sort(key=lambda item: (
            not item["enabled"],
            str(item["display_name"]).lower(),
            str(item["username"]).lower(),
        ))
        return {
            "users": users,
            "capabilities": enterprise_user_capabilities(principal),
            "roles": [
                {"key": "administrator", "label": "Administrador"},
                {"key": "analyst", "label": "Analista"},
                {"key": "viewer", "label": "Consulta"},
            ],
        }

    @router.post("/api/enterprise/users")
    def create_enterprise_user(
        body: EnterpriseUserCreateRequest,
        principal: Principal = Depends(require_permission("user:create")),
    ):
        role_key = body.role.strip().lower()
        role = _COMMERCIAL_USER_ROLES.get(role_key)
        if not role:
            raise HTTPException(status_code=400, detail="El rol seleccionado no es válido")
        username = body.username.strip().lower()
        display_name = body.display_name.strip()
        if not display_name or any(ord(char) < 32 for char in display_name):
            raise HTTPException(status_code=400, detail="El nombre del usuario no es válido")
        try:
            created = enterprise_identity.create_user(
                user_id=username,
                username=username,
                display_name=display_name,
                password=body.password,
                tenant_id=principal.company_id,
                roles=[role],
            )
        except IdentityError as exc:
            enterprise_user_identity_error(exc)
        except TenantRegistryError as exc:
            raise HTTPException(status_code=400, detail="La empresa no está disponible") from exc
        components.db.audit(
            "company.user.created",
            principal.company_id,
            principal.user_id,
            "user",
            details={"username": username, "role": role_key},
        )
        return {"ok": True, "user": enterprise_user_public(created, principal)}

    @router.patch("/api/enterprise/users/{username}")
    def update_enterprise_user(
        username: str,
        body: EnterpriseUserUpdateRequest,
        principal: Principal = Depends(require_permission("user:update")),
    ):
        actor = enterprise_user_actor(principal)
        target = enterprise_user_target(principal, username)
        changes: Dict[str, Any] = {}
        changed_fields: List[str] = []

        if body.display_name is not None:
            display_name = body.display_name.strip()
            if not display_name or any(ord(char) < 32 for char in display_name):
                raise HTTPException(status_code=400, detail="El nombre del usuario no es válido")
            changes["display_name"] = display_name
            changed_fields.append("display_name")

        if body.role is not None:
            if not enterprise_identity.has_permission(actor, "user:role_assign"):
                raise HTTPException(status_code=403, detail="No tienes permiso para cambiar roles")
            if target.get("user_id") == principal.user_id:
                raise HTTPException(status_code=403, detail="No puedes cambiar tu propio rol")
            if "SYSTEM_ADMIN" in set(target.get("roles") or []):
                raise HTTPException(status_code=403, detail="Este administrador está protegido")
            role_key = body.role.strip().lower()
            role = _COMMERCIAL_USER_ROLES.get(role_key)
            if not role:
                raise HTTPException(status_code=400, detail="El rol seleccionado no es válido")
            target_roles = set(target.get("roles") or [])
            if (
                "TENANT_ADMIN" in target_roles
                and role != "TENANT_ADMIN"
                and target.get("status") == "ACTIVE"
                and not enterprise_other_active_admin_exists(principal, target)
            ):
                raise HTTPException(
                    status_code=409,
                    detail="Debe existir al menos otro administrador activo",
                )
            changes["roles"] = [role]
            changed_fields.append("role")

        if not changes:
            raise HTTPException(status_code=400, detail="No hay cambios para guardar")

        try:
            updated = enterprise_identity.update(target["user_id"], **changes)
        except IdentityError as exc:
            enterprise_user_identity_error(exc)

        components.db.audit(
            "company.user.updated",
            principal.company_id,
            principal.user_id,
            "user",
            details={"username": target.get("username"), "fields": changed_fields},
        )
        return {"ok": True, "user": enterprise_user_public(updated, principal)}

    @router.put("/api/enterprise/users/{username}/status")
    def set_enterprise_user_status(
        username: str,
        body: EnterpriseUserStatusRequest,
        principal: Principal = Depends(require_permission("user:disable")),
    ):
        target = enterprise_user_target(principal, username)
        if target.get("user_id") == principal.user_id:
            raise HTTPException(status_code=403, detail="No puedes desactivar tu propio acceso")
        if "SYSTEM_ADMIN" in set(target.get("roles") or []):
            raise HTTPException(status_code=403, detail="Este administrador está protegido")
        if (
            not body.enabled
            and target.get("status") == "ACTIVE"
            and "TENANT_ADMIN" in set(target.get("roles") or [])
            and not enterprise_other_active_admin_exists(principal, target)
        ):
            raise HTTPException(
                status_code=409,
                detail="Debe existir al menos otro administrador activo",
            )
        try:
            updated = enterprise_identity.set_status(
                target["user_id"],
                "ACTIVE" if body.enabled else "DISABLED",
            )
        except IdentityError as exc:
            enterprise_user_identity_error(exc)
        components.db.audit(
            "company.user.status_changed",
            principal.company_id,
            principal.user_id,
            "user",
            details={"username": target.get("username"), "enabled": body.enabled},
        )
        return {"ok": True, "user": enterprise_user_public(updated, principal)}

    def data_connection_scope(principal: Principal) -> Dict[str, Any]:
        """Resolve the company namespace solely from the authenticated user."""
        actor = enterprise_user_actor(principal)
        return enterprise_onboarding.sql.company_scope(enterprise_identity.scope(actor))

    def public_data_connection(record: Dict[str, Any]) -> Dict[str, Any]:
        tested = record.get("last_test_status") == "PASS"
        enabled = bool(record.get("enabled"))
        return {
            "handle": record.get("connection_id"),
            "name": record.get("display_name") or record.get("connection_id"),
            "database": record.get("database"),
            "authentication_label": "Usar acceso de Windows" if record.get("auth_mode") == "WINDOWS_INTEGRATED" else "Usar usuario y contraseña",
            "enabled": enabled,
            "status_label": "Verificado" if tested else ("Requiere atención" if enabled else "Desactivada"),
            "verified": tested,
            "last_verified_at": record.get("last_test_at"),
            "tables_count": len(record.get("allowed_tables") or []),
            "credential_configured": bool(record.get("secret_reference")) or record.get("auth_mode") == "WINDOWS_INTEGRATED",
            "capabilities": {"read_only": bool(record.get("read_only")), "authorized_sources": len(record.get("allowed_tables") or [])},
        }

    def data_connection_error(exc: EnterpriseSqlError) -> None:
        status = 404 if exc.code == "SQL_CONNECTION_NOT_FOUND" else 400
        message = {
            "SQL_CONNECTION_NOT_FOUND": "No se encontró la conexión solicitada",
            "SQL_ALLOWLIST_REQUIRED": "Selecciona al menos una fuente autorizada",
            "SQL_CONNECTION_ALREADY_EXISTS": "Ya existe una conexión con ese nombre",
            "SQL_CONNECTION_DISABLED": "La conexión está desactivada",
            "SQL_SECRET_UNAVAILABLE": "No se pudo guardar la credencial de forma segura",
            "SQL_AUTH_FAILED": "No se pudo verificar el acceso a los datos",
            "SQL_TIMEOUT": "La conexión tardó demasiado en responder",
            "SQL_DATABASE_UNAVAILABLE": "No se pudo acceder a la base de datos",
        }.get(exc.code, "No se pudo completar la operación con esta conexión")
        raise HTTPException(status_code=status, detail=message) from exc

    def data_connection_sources(values: List[str]) -> tuple[List[str], List[str]]:
        tables = [str(value).strip() for value in values if str(value).strip()]
        schemas = sorted({value.split(".", 1)[0] for value in tables if "." in value})
        if not tables or not schemas:
            raise HTTPException(status_code=400, detail="Selecciona fuentes autorizadas con el formato área.tabla")
        return schemas, tables

    def data_connection_provider() -> SqlServerPyodbcProvider:
        # Password material remains in Windows Credential Manager; it is never
        # persisted in the profile, response, audit record, or trace.
        return SqlServerPyodbcProvider(EnterpriseSecretStore(WindowsCredentialSecretProvider()))



    connected_sql_bridge = GovernedSqlAssistantBridge(
        store=enterprise_onboarding.sql,
        provider_factory=data_connection_provider,
    )

    def resolve_connected_sql(
        principal: Principal,
        question: str,
    ):
        actor = enterprise_user_actor(principal)

        if not enterprise_identity.has_permission(
            actor,
            "sql:read",
        ):
            return None

        analytics = (
            getattr(
                components,
                "analytics",
                None,
            )
            or getattr(
                components,
                "analytic_rules",
                None,
            )
        )

        analytic_bindings = (
            analytics.applicable_bindings(
                principal
            )
            if analytics is not None
            else []
        )

        return connected_sql_bridge.resolve(
            scope=data_connection_scope(principal),
            question=question,
            analytic_bindings=
                analytic_bindings,
        )

    components.service.connected_sql_resolver = resolve_connected_sql

    @router.post(
        "/api/enterprise/data-connections/probe"
    )
    def probe_data_connection(
        body: DataConnectionProbeRequest,
        principal: Principal = Depends(
            require_permission(
                "sql:configure"
            )
        ),
    ):
        scope = data_connection_scope(
            principal
        )

        authentication = (
            str(
                body.authentication
                or ""
            )
            .strip()
            .lower()
        )

        if authentication not in {
            "windows",
            "password",
        }:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Selecciona una forma "
                    "de acceso válida"
                ),
            )

        username = str(
            body.username
            or ""
        ).strip()

        if (
            authentication == "password"
            and (
                not username
                or not body.password
            )
        ):
            raise HTTPException(
                status_code=400,
                detail=(
                    "Indica el usuario y "
                    "la contraseña para continuar"
                ),
            )

        class _RequestLocalSecretProvider:
            def __init__(self):
                self.values: Dict[str, str] = {}

            def set(
                self,
                reference: str,
                value: str,
            ) -> None:
                self.values[
                    str(reference)
                ] = str(value)

            def get(
                self,
                reference: str,
            ) -> Optional[str]:
                return self.values.get(
                    str(reference)
                )

            def delete(
                self,
                reference: str,
            ) -> None:
                self.values.pop(
                    str(reference),
                    None,
                )

            def clear(self) -> None:
                self.values.clear()

        transient_backend = (
            _RequestLocalSecretProvider()
        )

        transient_store = (
            EnterpriseSecretStore(
                transient_backend
            )
        )

        transient_reference = ""

        try:
            if authentication == "password":
                transient_reference = (
                    "request-local"
                )

                transient_store.set(
                    transient_reference,
                    body.password or "",
                )

            profile = (
                build_transient_sql_probe_profile(
                    server=body.server,
                    database=body.database,
                    auth_mode=(
                        "SQL_AUTH"
                        if authentication
                        == "password"
                        else "WINDOWS_INTEGRATED"
                    ),
                    username=username,
                    secret_reference=(
                        transient_reference
                    ),
                        trust_server_certificate=(
                            body.trust_server_certificate
                        ),
                )
            )

            provider = (
                SqlServerPyodbcProvider(
                    transient_store
                )
            )

            result = (
                probe_sql_server_metadata(
                    provider,
                    profile,
                )
            )

        except EnterpriseSqlError as exc:
            data_connection_error(
                exc
            )

            raise HTTPException(
                status_code=400,
                detail=(
                    "No se pudo verificar "
                    "la conexión"
                ),
            ) from exc

        finally:
            if transient_reference:
                try:
                    transient_store.delete(
                        transient_reference
                    )
                except EnterpriseSqlError:
                    pass

            transient_backend.clear()

        components.db.audit(
            "data_connection.probe",
            scope["company_id"],
            principal.user_id,
            "data_connection",
            details={
                "status":
                    result.get(
                        "status"
                    ),
                "discovered_object_count":
                    result.get(
                        "discovered_object_count",
                        0,
                    ),
                "authentication":
                    authentication,
            },
        )

        return {
            "ok": True,
            "status":
                result.get(
                    "status"
                ),
            "objects":
                result.get(
                    "objects",
                    [],
                ),
            "discovered_object_count":
                result.get(
                    "discovered_object_count",
                    0,
                ),
        }


    @router.get("/api/enterprise/data-connections")
    def list_data_connections(principal: Principal = Depends(require_permission("sql:read"))):
        scope = data_connection_scope(principal)
        profiles = enterprise_onboarding.sql.list(scope)
        return {"connections": [public_data_connection(item) for item in profiles]}

    @router.post("/api/enterprise/data-connections")
    def create_data_connection(
        body: DataConnectionCreateRequest,
        principal: Principal = Depends(require_permission("sql:configure")),
    ):
        scope = data_connection_scope(principal)
        auth = body.authentication.strip().lower()
        if auth not in {"windows", "password"}:
            raise HTTPException(status_code=400, detail="Selecciona una forma de acceso válida")
        if auth == "password" and (not body.username or not body.password):
            raise HTTPException(status_code=400, detail="Indica el usuario y la contraseña para continuar")
        schemas, tables = data_connection_sources(body.allowed_sources)
        reference = ""
        secrets = None
        try:
            if auth == "password":
                reference = "sql:" + uuid.uuid4().hex
                secrets = EnterpriseSecretStore(WindowsCredentialSecretProvider())
                secrets.set(reference, body.password or "")
            record = enterprise_onboarding.sql.register(
                scope=scope,
                connection_id="connection-" + uuid.uuid4().hex,
                display_name=body.display_name.strip(),
                server=body.server.strip(), database=body.database.strip(),
                auth_mode="WINDOWS_INTEGRATED" if auth == "windows" else "SQL_AUTH",
                username=(body.username or "").strip(), secret_reference=reference,
                allowed_schemas=schemas, allowed_tables=tables,
                trust_server_certificate=body.trust_server_certificate,
            )
        except EnterpriseSqlError as exc:
            if reference and secrets:
                try: secrets.delete(reference)
                except EnterpriseSqlError: pass
            data_connection_error(exc)
        components.db.audit("company.data_connection.created", principal.company_id, principal.user_id, "data_connection", details={"name": body.display_name.strip(), "authentication": auth})
        return {"ok": True, "connection": public_data_connection(record)}

    @router.patch("/api/enterprise/data-connections/{handle}")
    def update_data_connection(
        handle: str,
        body: DataConnectionUpdateRequest,
        principal: Principal = Depends(require_permission("sql:configure")),
    ):
        scope = data_connection_scope(principal)
        changes = body.model_dump(exclude_none=True)
        if "allowed_sources" in changes:
            schemas, tables = data_connection_sources(changes.pop("allowed_sources"))
            changes["allowed_schemas"], changes["allowed_tables"] = schemas, tables
        if not changes:
            raise HTTPException(status_code=400, detail="No hay cambios para guardar")
        try:
            record = enterprise_onboarding.sql.update(scope, handle, **changes)
        except EnterpriseSqlError as exc:
            data_connection_error(exc)
        components.db.audit("company.data_connection.updated", principal.company_id, principal.user_id, "data_connection", details={"fields": sorted(changes)})
        return {"ok": True, "connection": public_data_connection(record)}

    @router.put("/api/enterprise/data-connections/{handle}/status")
    def set_data_connection_status(
        handle: str,
        body: DataConnectionStatusRequest,
        principal: Principal = Depends(require_permission("sql:configure")),
    ):
        scope = data_connection_scope(principal)
        try:
            record = enterprise_onboarding.sql.enable(scope, handle) if body.enabled else enterprise_onboarding.sql.disable(scope, handle)
        except EnterpriseSqlError as exc:
            data_connection_error(exc)
        components.db.audit("company.data_connection.status_changed", principal.company_id, principal.user_id, "data_connection", details={"enabled": bool(body.enabled)})
        return {"ok": True, "connection": public_data_connection(record)}

    @router.post("/api/enterprise/data-connections/{handle}/test")
    def test_data_connection(handle: str, principal: Principal = Depends(require_permission("sql:configure"))):
        scope = data_connection_scope(principal)
        try:
            result = test_connection(enterprise_onboarding.sql, data_connection_provider(), scope, handle)
            record = enterprise_onboarding.sql.get(scope, handle)
        except EnterpriseSqlError as exc:
            data_connection_error(exc)
        return {"ok": True, "connection": public_data_connection(record), "verified": result.get("status") == "PASS"}

    @router.post("/api/enterprise/data-connections/{handle}/discover")
    def discover_data_connection(handle: str, principal: Principal = Depends(require_permission("sql:read"))):
        scope = data_connection_scope(principal)
        try:
            result = discover_schema(enterprise_onboarding.sql, data_connection_provider(), scope, handle)
        except EnterpriseSqlError as exc:
            data_connection_error(exc)
        return {"ok": True, "sources": result.get("objects", [])}

    def commercial_ai_payload(principal: Principal, *, verification: Optional[str] = None) -> Dict[str, Any]:
        """Return only commercial configuration fields, never transport internals."""
        effective = enterprise_platform.resolve_effective_config(principal.company_id)
        configured = dict(effective.get("ai_provider") or {})
        kind = str(configured.get("provider_type") or "DISABLED").upper()
        enabled = bool(configured.get("enabled")) and kind != "DISABLED"
        model = configured.get("model") or None
        if kind == "DISABLED":
            state, label = "CONFIGURED", "Desactivada"
        elif not model:
            state, label = "BLOCKED", "Requiere configuración"
        elif verification == "PASS":
            state, label = "TESTED", "Verificada"
        elif verification in {"UNAVAILABLE", "TIMEOUT"}:
            state, label = "DEGRADED", "Requiere atención"
        else:
            state, label = "CONFIGURED", "Configurada"
        engine = {"OLLAMA": "ollama", "OPENAI_COMPATIBLE_LOCAL": "local-compatible", "DISABLED": "disabled"}.get(kind, "disabled")
        return {
            "state": state,
            "status_label": label,
            "enabled": enabled,
            "engine": engine,
            "engine_label": {"ollama": "Ollama", "local-compatible": "Motor local compatible", "disabled": "Sin inteligencia artificial"}[engine],
            "model": model,
            "can_edit": enterprise_identity.has_permission(enterprise_identity.get(principal.user_id), "config:write"),
        }

    def commercial_ai_config(body: AiConfigurationRequest, require_model: bool = True) -> Dict[str, Any]:
        engine = body.engine.strip().lower()
        model = (body.model or "").strip() or None
        presets = {
            "ollama": ("OLLAMA", "http://127.0.0.1:11434"),
            "local-compatible": ("OPENAI_COMPATIBLE_LOCAL", "http://127.0.0.1:1234/v1"),
        }
        if engine == "disabled":
            return {"provider_id": "disabled", "provider_type": "DISABLED", "base_url": None, "model": None, "enabled": False, "timeout": 30, "context_window": None}
        if engine not in presets:
            raise HTTPException(status_code=400, detail="Selecciona un motor local y un modelo para continuar")
        if require_model and not model:
            raise HTTPException(status_code=400, detail="Selecciona un motor local y un modelo para continuar")
        provider_type, base_url = presets[engine]
        return {"provider_id": engine, "provider_type": provider_type, "base_url": base_url, "model": model, "enabled": True, "timeout": 30, "context_window": None}

    @router.get("/api/enterprise/ai-configuration")
    def get_commercial_ai_configuration(principal: Principal = Depends(require_permission("config:read"))):
        return {"configuration": commercial_ai_payload(principal)}

    @router.post("/api/enterprise/ai-configuration/detect")
    def detect_commercial_ai_models(
        body: Optional[AiConfigurationRequest] = None,
        principal: Principal = Depends(require_permission("config:read")),
    ):
        if body is None:
            effective = enterprise_platform.resolve_effective_config(principal.company_id)
            provider = effective.get("ai_provider") or {}
        else:
            provider = commercial_ai_config(body, require_model=False)
        result = enterprise_platform.discover_models(provider, _CommercialAiAdapter())
        state = str(result.get("status") or "UNAVAILABLE")
        return {
            "status": state,
            "status_label": {"PASS": "Opciones detectadas", "EMPTY": "No se encontraron modelos", "DISABLED": "La inteligencia artificial está desactivada", "TIMEOUT": "La búsqueda tardó demasiado", "UNAVAILABLE": "El motor local no está disponible", "UNSUPPORTED": "La detección no está disponible"}.get(state, "No se pudieron detectar opciones"),
            "models": [{"id": item["id"], "name": item["name"]} for item in result.get("models", [])],
        }

    @router.put("/api/enterprise/ai-configuration")
    def save_commercial_ai_configuration(
        body: AiConfigurationRequest,
        principal: Principal = Depends(require_permission("config:write")),
    ):
        provider = commercial_ai_config(body)
        current = enterprise_platform.resolve_effective_config(principal.company_id)
        features = dict(current.get("enabled_features") or {})
        features["ai_enabled"] = bool(provider["enabled"])
        enterprise_platform.update_tenant(principal.company_id, {"ai_provider": provider, "enabled_features": features})
        components.db.audit("company.ai_configuration.saved", principal.company_id, principal.user_id, "ai_configuration", details={"engine": body.engine.strip().lower(), "enabled": bool(provider["enabled"])})
        return {"ok": True, "configuration": commercial_ai_payload(principal)}

    @router.post("/api/enterprise/ai-configuration/test")
    def test_commercial_ai_configuration(
        body: Optional[AiConfigurationRequest] = None,
        principal: Principal = Depends(require_permission("config:read")),
    ):
        if body is None:
            effective = enterprise_platform.resolve_effective_config(principal.company_id)
            provider = effective.get("ai_provider") or {}
        else:
            provider = commercial_ai_config(body)
        try:
            result = enterprise_platform.test_provider(provider, _CommercialAiAdapter())
            verification = "PASS" if result.get("status") == "PASS" else None
            configuration = commercial_ai_payload(principal, verification=verification)
            if body is not None:
                configuration = {
                    **configuration,
                    "engine": body.engine.strip().lower(),
                    "model": body.model.strip() if body.model else None,
                }
            return {"ok": True, "configuration": configuration}
        except PlatformConfigError as exc:
            status = "TIMEOUT" if exc.code == "AI_PROVIDER_TIMEOUT" else "UNAVAILABLE"
            configuration = commercial_ai_payload(principal, verification=status)
            if body is not None:
                configuration = {
                    **configuration,
                    "engine": body.engine.strip().lower(),
                    "model": body.model.strip() if body.model else None,
                }
            return {"ok": False, "configuration": configuration, "message": "No se pudo verificar el motor local"}

    def commercial_appearance_payload(principal: Principal) -> Dict[str, Any]:
        public = enterprise_platform.public_effective_config(principal.company_id)
        user = enterprise_identity.get(principal.user_id)
        return {
            "theme": public.get("theme") or "professional-light",
            "accent_color": public.get("accent_color") or "#1d67d2",
            "can_edit": enterprise_identity.has_permission(user, "config:write"),
        }

    @router.get("/api/enterprise/appearance")
    def get_commercial_appearance(principal: Principal = Depends(require_permission("config:read"))):
        return {"appearance": commercial_appearance_payload(principal)}

    @router.put("/api/enterprise/appearance")
    def save_commercial_appearance(
        body: AppearanceRequest,
        principal: Principal = Depends(require_permission("config:write")),
    ):
        current = enterprise_platform.tenant_config(principal.company_id)
        branding = dict(current.get("branding") or {})
        branding.update({"theme": body.theme, "accent_color": body.accent_color})
        try:
            enterprise_platform.update_tenant(principal.company_id, {"theme": body.theme, "branding": branding})
        except PlatformConfigError as exc:
            raise HTTPException(status_code=400, detail="La apariencia seleccionada no es válida") from exc
        components.db.audit("company.appearance.saved", principal.company_id, principal.user_id, "appearance", details={"theme": body.theme})
        return {"ok": True, "appearance": commercial_appearance_payload(principal)}

    @router.get("/api/enterprise/security-recovery")
    def commercial_security_recovery(principal: Principal = Depends(principal_dependency)):
        user = enterprise_identity.get(principal.user_id)
        can_backup = enterprise_identity.has_permission(user, "backup:create")
        can_restore = enterprise_identity.has_permission(user, "backup:restore")
        return {"protection": "Configurada", "backup_available": can_backup, "recovery_available": can_restore}

    @router.post("/api/enterprise/security-recovery/backup")
    def create_commercial_backup(principal: Principal = Depends(require_permission("backup:create"))):
        handle = tempfile.NamedTemporaryFile(prefix="ia-enterprise-backup-", suffix=".zip", delete=False)
        handle.close()
        output = Path(handle.name)
        try:
            governed_backup(components.cfg.root, output)
        except BackupError as exc:
            output.unlink(missing_ok=True)
            raise HTTPException(status_code=400, detail="No se pudo crear el respaldo") from exc
        components.db.audit("company.backup.created", principal.company_id, principal.user_id, "backup", details={})
        def stream_backup():
            with output.open("rb") as backup_stream:
                while chunk := backup_stream.read(1024 * 1024):
                    yield chunk
        return StreamingResponse(stream_backup(), media_type="application/zip", headers={"Content-Disposition": "attachment; filename=IA-Empresarial-Local-respaldo.zip"}, background=BackgroundTask(output.unlink, missing_ok=True))

    @router.post("/api/enterprise/security-recovery/restore")
    async def restore_commercial_backup(
        body: RecoveryRequest = Depends(),
        archive: UploadFile = File(...),
        principal: Principal = Depends(require_permission("backup:restore")),
    ):
        if not body.confirmed:
            raise HTTPException(
                status_code=400,
                detail="Confirma la recuperación para continuar",
            )

        temp = tempfile.NamedTemporaryFile(
            prefix="ia-enterprise-restore-",
            suffix=".zip",
            delete=False,
        )
        source = Path(temp.name)
        restore_error = None

        try:
            with temp:
                shutil.copyfileobj(
                    archive.file,
                    temp,
                )

            _close_enterprise_components()

            try:
                governed_restore(
                    components.cfg.root,
                    source,
                )
            except (
                BackupError,
                OSError,
                shutil.Error,
                zipfile.BadZipFile,
            ) as exc:
                restore_error = exc
            finally:
                try:
                    _reload_enterprise_components()
                except Exception as exc:
                    raise HTTPException(
                        status_code=500,
                        detail="No se pudo reactivar el servicio después de la recuperación",
                    ) from exc

            if restore_error is not None:
                raise HTTPException(
                    status_code=400,
                    detail="No se pudo recuperar el respaldo",
                ) from restore_error

        finally:
            source.unlink(missing_ok=True)

        components.db.audit(
            "company.backup.restored",
            principal.company_id,
            principal.user_id,
            "backup",
            details={},
        )

        return {
            "ok": True,
            "message": "La información se recuperó correctamente",
        }
    @router.get("/api/enterprise/advanced-preferences")
    def get_advanced_preferences(principal: Principal = Depends(require_permission("config:read"))):
        effective = enterprise_platform.resolve_effective_config(principal.company_id)
        user = enterprise_identity.get(principal.user_id)
        return {"preferences": {"locale": effective.get("locale") or effective.get("default_locale"), "timezone": effective.get("timezone") or effective.get("default_timezone"), "can_edit": enterprise_identity.has_permission(user, "config:write")}}

    @router.put("/api/enterprise/advanced-preferences")
    def save_advanced_preferences(body: AdvancedPreferencesRequest, principal: Principal = Depends(require_permission("config:write"))):
        enterprise_platform.update_tenant(principal.company_id, {"locale": body.locale.strip(), "timezone": body.timezone.strip()})
        components.db.audit("company.advanced_preferences.saved", principal.company_id, principal.user_id, "advanced_preferences", details={})
        return get_advanced_preferences(principal)


    @router.post("/api/enterprise/readiness/validate")
    def validate_commercial_readiness(
        principal: Principal = Depends(
            require_permission("config:write")
        ),
    ):
        initial = enterprise_onboarding.readiness(
            principal.company_id
        )

        sql_step = (
            initial.get("steps", {})
            .get("sql", {})
        )

        sql_verification = {
            "status": "NOT_REQUIRED",
            "configured_count": 0,
            "tested_count": 0,
        }

        if sql_step.get("required"):
            user = enterprise_identity.get(
                principal.user_id
            )

            if not (
                enterprise_identity
                .has_permission(
                    user,
                    "sql:configure",
                )
                and enterprise_identity
                .has_permission(
                    user,
                    "sql:read",
                )
            ):
                raise HTTPException(
                    status_code=403,
                    detail=
                        "No tienes permiso para validar los datos",
                )

            scope = data_connection_scope(
                principal
            )

            profiles = [
                profile
                for profile
                in enterprise_onboarding.sql.list(
                    scope
                )
                if profile.get("enabled")
                and profile.get("read_only")
            ]

            for profile in profiles:
                handle = str(
                    profile.get(
                        "connection_id"
                    )
                    or ""
                ).strip()

                if not handle:
                    continue

                try:
                    test_connection(
                        enterprise_onboarding.sql,
                        data_connection_provider(),
                        scope,
                        handle,
                    )

                    discover_schema(
                        enterprise_onboarding.sql,
                        data_connection_provider(),
                        scope,
                        handle,
                    )

                except EnterpriseSqlError:
                    continue

            after_sql = (
                enterprise_onboarding
                .readiness(
                    principal.company_id
                )
            )

            final_sql = (
                after_sql.get(
                    "steps", {}
                )
                .get("sql", {})
            )

            sql_verification = {
                "status": (
                    "PASS"
                    if final_sql.get(
                        "status"
                    ) == "TESTED"
                    else "FAIL"
                ),
                "configured_count": (
                    final_sql.get(
                        "configured_count"
                    )
                    or 0
                ),
                "tested_count": (
                    final_sql.get(
                        "tested_count"
                    )
                    or 0
                ),
            }
        else:
            after_sql = initial

        ai_step = (
            after_sql.get("steps", {})
            .get("ai", {})
        )

        ai_test = {
            "status": "NOT_REQUIRED",
        }

        if ai_step.get("required"):
            effective = (
                enterprise_platform
                .resolve_effective_config(
                    principal.company_id
                )
            )

            provider = (
                effective.get(
                    "ai_provider"
                )
                or {}
            )

            try:
                ai_test = (
                    enterprise_platform
                    .test_provider(
                        provider,
                        _CommercialAiAdapter(),
                    )
                )

            except PlatformConfigError as exc:
                ai_test = {
                    "status": (
                        "TIMEOUT"
                        if exc.code
                        == "AI_PROVIDER_TIMEOUT"
                        else "UNAVAILABLE"
                    ),
                }

        readiness = (
            enterprise_onboarding
            .readiness(
                principal.company_id,
                ai_test=ai_test,
            )
        )

        components.db.audit(
            "company.readiness.validated",
            principal.company_id,
            principal.user_id,
            "readiness",
            details={
                "status":
                    readiness.get("status"),
                "verification_status":
                    readiness.get(
                        "verification_status"
                    ),
                "sql_status":
                    sql_verification.get(
                        "status"
                    ),
                "ai_status":
                    ai_test.get("status"),
            },
        )

        return {
            "ok": (
                readiness.get("status")
                == "READY"
            ),
            "readiness": {
                "status":
                    readiness.get("status"),
                "verification_status":
                    readiness.get(
                        "verification_status"
                    ),
                "steps":
                    readiness.get("steps")
                    or {},
                "next_actions":
                    readiness.get(
                        "next_actions"
                    )
                    or [],
            },
            "verification": {
                "sql":
                    sql_verification,
                "ai": {
                    "status":
                        ai_test.get(
                            "status"
                        ),
                },
            },
        }

    @router.get("/api/enterprise/app-context")
    def product_app_context(
        principal: Principal = Depends(
            principal_dependency
        ),
    ):
        try:
            user = enterprise_identity.get(
                principal.user_id
            )
        except IdentityError as exc:
            raise HTTPException(
                status_code=401,
                detail="Sesión empresarial inválida",
            ) from exc

        if (
            user["tenant_id"]
            != principal.company_id
        ):
            raise HTTPException(
                status_code=403,
                detail="Acceso empresarial no permitido",
            )

        public_config = (
            enterprise_platform
            .public_effective_config(
                principal.company_id
            )
        )

        readiness = (
            enterprise_onboarding.readiness(
                principal.company_id
            )
        )

        permissions = set(
            enterprise_identity
            .effective_permissions(
                user
            )
            or []
        )

        settings_permissions = {
            "config:read",
            "config:write",
            "tenant:list",
            "tenant:update",
            "user:list",
            "user:create",
            "sql:read",
            "sql:configure",
            "backup:create",
        }

        settings_visible = (
            "*" in permissions
            or bool(
                permissions
                & settings_permissions
            )
        )

        configure_data = (
            "*" in permissions
            or "sql:configure" in permissions
            or "config:write" in permissions
        )

        roles = set(
            user.get("roles")
            or []
        )

        if roles & {
            "SYSTEM_ADMIN",
            "TENANT_ADMIN",
        }:
            role_label = "Administrador"
        elif "ANALYST" in roles:
            role_label = "Analista"
        else:
            role_label = "Consulta"

        return {
            "user": {
                "user_id": user.get(
                    "user_id"
                ),
                "username": user.get(
                    "username"
                ),
                "display_name": user.get(
                    "display_name"
                ),
                "role_label": role_label,
            },
            "company": {
                "display_name": (
                    public_config.get(
                        "display_name"
                    )
                    or "IA Empresarial Local"
                ),
                "theme": (
                    public_config.get(
                        "theme"
                    )
                    or "professional-light"
                ),
                "accent_color": (
                    public_config.get(
                        "accent_color"
                    )
                ),
                "logo_reference": (
                    public_config.get(
                        "logo_reference"
                    )
                ),
                "business_type": (
                    public_config.get(
                        "business_type"
                    )
                    or "Otro"
                ),
            },
            "readiness": {
                "status": readiness.get(
                    "status"
                ),
                "verification_status": (
                    readiness.get(
                        "verification_status"
                    )
                ),
                "steps": (
                    readiness.get(
                        "steps"
                    )
                    or {}
                ),
                "next_actions": (
                    readiness.get(
                        "next_actions"
                    )
                    or []
                ),
            },
            "capabilities": {
                "settings": (
                    settings_visible
                ),
                "configure_data": (
                    configure_data
                ),
            },
        }



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
    def enterprise_diagnostics(principal: Principal = Depends(require_permission("admin:audit"))):
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

    @router.get("/api/enterprise/control-plane/overview")
    def control_plane_overview(principal: Principal = Depends(principal_dependency)):
        health = {"live": True, "readiness": "available" if components.llm.healthy() else "degraded",
                  "llm_healthy": bool(components.llm.healthy()), "vector_store": type(components.vectors).__name__}
        return control_plane_response(lambda: control_plane.overview(principal, health=health))

    @router.get("/api/enterprise/control-plane/tenants")
    def control_plane_tenants(principal: Principal = Depends(principal_dependency)):
        return {"tenants": control_plane_response(lambda: control_plane.tenants_for(principal))}

    @router.get("/api/enterprise/control-plane/users")
    def control_plane_users(principal: Principal = Depends(principal_dependency)):
        return {"users": control_plane_response(lambda: control_plane.users_for(principal))}

    @router.get("/api/enterprise/control-plane/sql-sources")
    def control_plane_sql_sources(principal: Principal = Depends(principal_dependency)):
        return {"sources": control_plane_response(lambda: control_plane.sql_sources_for(principal))}

    @router.get("/api/enterprise/control-plane/ai")
    def control_plane_ai(principal: Principal = Depends(principal_dependency)):
        return {"provider": control_plane_response(lambda: control_plane.ai_for(principal))}

    @router.post("/api/enterprise/chat")
    def enterprise_chat(body: ChatRequest, principal: Principal = Depends(require_permission("analysis:run"))):
        try:
            with components.traceability.scope(principal, trace_type="chat", prompt=body.message) as trace_id:
                result = components.service.chat(principal, body.message, body.history)
                components.traceability.add_step(trace_id, "response_delivery", engine=getattr(components.llm, "name", "local"), details={"sources_count": len(result.get("sources") or [])})
                result["trace_id"] = trace_id
                return result
        except Exception as exc:
            components.db.audit("chat.http_error", principal.company_id, principal.user_id, "query", outcome="error", details={"error_type": type(exc).__name__})
            components.logger.exception("chat http error", extra={"event": "chat.http_error", "company_id": principal.company_id, "user_id": principal.user_id, "error_type": type(exc).__name__})
            return JSONResponse({"ok": False, "error": "No se pudo completar la solicitud con el servicio local."}, status_code=500)

    @router.post("/api/enterprise/chat/stream")
    def enterprise_chat_stream(
        body: ChatRequest,
        principal: Principal = Depends(
            require_permission("analysis:run")
        ),
    ):
        def events():
            trace_id = components.traceability.start(
                principal,
                trace_type="chat_stream",
                prompt=body.message,
            )
            trace_finished = False
            stream_iter = None

            def finish_trace(
                status="completed",
                *,
                error_type=None,
                error_message=None,
            ):
                nonlocal trace_finished

                if trace_finished:
                    return

                if status == "error":
                    components.traceability.add_step(
                        trace_id,
                        "error",
                        engine="runtime",
                        details={
                            "error_type": error_type,
                            "error": (
                                error_message or ""
                            )[:500],
                        },
                    )
                elif status == "cancelled":
                    components.traceability.add_step(
                        trace_id,
                        "cancelled",
                        engine="runtime",
                    )

                components.traceability.complete(
                    trace_id,
                    status=status,
                )
                trace_finished = True

            def close_stream():
                nonlocal stream_iter

                if stream_iter is None:
                    return

                closer = getattr(
                    stream_iter,
                    "close",
                    None,
                )

                if closer is not None:
                    with components.traceability.bind(
                        trace_id
                    ):
                        closer()

                stream_iter = None

            try:
                stream_iter = iter(
                    components.service.stream_general(
                        principal,
                        body.message,
                        body.history,
                    )
                )

                streamed = False
                fallback = False

                while True:
                    try:
                        # Cada reanudación del generador recibe el contexto
                        # de trazabilidad únicamente durante este tramo
                        # síncrono. El token se libera antes del yield HTTP.
                        with components.traceability.bind(
                            trace_id
                        ):
                            event = next(stream_iter)
                    except StopIteration:
                        break

                    event_type = event.get("type")

                    if event_type == "fallback":
                        fallback = True
                        close_stream()
                        break

                    streamed = True

                    if event_type == "error":
                        event = {
                            **event,
                            "trace_id": trace_id,
                        }

                        finish_trace(
                            "error",
                            error_type=str(
                                event.get("error_type")
                                or "StreamError"
                            ),
                            error_message=str(
                                event.get("message")
                                or ""
                            ),
                        )

                        yield json.dumps(
                            event,
                            ensure_ascii=False,
                        ) + "\n"
                        return

                    if event_type == "done":
                        event = {
                            **event,
                            "trace_id": trace_id,
                        }

                        components.traceability.add_step(
                            trace_id,
                            "response_delivery",
                            engine=getattr(
                                components.llm,
                                "name",
                                "local",
                            ),
                            details={
                                "sources_count": len(
                                    event.get("sources")
                                    or []
                                )
                            },
                        )

                        close_stream()
                        finish_trace("completed")

                        yield json.dumps(
                            event,
                            ensure_ascii=False,
                        ) + "\n"
                        return

                    # Este yield ocurre sin un ContextVar token abierto.
                    yield json.dumps(
                        event,
                        ensure_ascii=False,
                    ) + "\n"

                if fallback or not streamed:
                    yield json.dumps(
                        {
                            "type": "status",
                            "phase": "retrieval",
                            "message": (
                                "Consultando evidencia empresarial..."
                            ),
                        },
                        ensure_ascii=False,
                    ) + "\n"

                    # ContextEngine, reglas analíticas y structured_data
                    # conservan trace_step() gracias a bind(), pero este
                    # contexto termina antes de entregar el done.
                    with components.traceability.bind(
                        trace_id
                    ):
                        result = components.service.chat(
                            principal,
                            body.message,
                            body.history,
                        )

                    result = {
                        **result,
                        "type": "done",
                        "trace_id": trace_id,
                    }

                    components.traceability.add_step(
                        trace_id,
                        "response_delivery",
                        engine=getattr(
                            components.llm,
                            "name",
                            "local",
                        ),
                        details={
                            "sources_count": len(
                                result.get("sources")
                                or []
                            )
                        },
                    )

                    finish_trace("completed")

                    yield json.dumps(
                        result,
                        ensure_ascii=False,
                    ) + "\n"
                    return

                raise RuntimeError(
                    "stream ended without terminal event"
                )

            except GeneratorExit:
                try:
                    close_stream()
                finally:
                    if not trace_finished:
                        try:
                            finish_trace("cancelled")
                        except Exception:
                            pass
                raise

            except Exception as exc:
                try:
                    close_stream()
                except Exception:
                    pass

                if not trace_finished:
                    try:
                        finish_trace(
                            "error",
                            error_type=type(exc).__name__,
                            error_message=str(exc),
                        )
                    except Exception:
                        pass

                components.db.audit(
                    "chat.stream_error",
                    principal.company_id,
                    principal.user_id,
                    "query",
                    outcome="error",
                    details={
                        "error_type": type(exc).__name__
                    },
                )

                components.logger.exception(
                    "chat stream error",
                    extra={
                        "event": "chat.stream_error",
                        "company_id": principal.company_id,
                        "user_id": principal.user_id,
                        "error_type": type(exc).__name__,
                    },
                )

                yield json.dumps(
                    {
                        "type": "error",
                        "trace_id": trace_id,
                        "message": (
                            "No se pudo completar la respuesta "
                            "con el servicio local."
                        ),
                    },
                    ensure_ascii=False,
                ) + "\n"

        return StreamingResponse(
            events(),
            media_type="application/x-ndjson",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )


    @router.get("/api/enterprise/memories")
    def list_memories(include_inactive: bool = False, principal: Principal = Depends(require_permission("knowledge:read"))):
        return {"memories": components.memory.list(principal, include_inactive=include_inactive)}

    @router.get("/api/enterprise/memories/search")
    def search_memories(q: str, limit: int = 20, principal: Principal = Depends(require_permission("knowledge:read"))):
        return {"memories": components.memory.search(principal, q, limit=max(1, min(limit, 50)), min_score=0.0)}

    @router.post("/api/enterprise/memories")
    def create_memory(body: MemoryCreateRequest, principal: Principal = Depends(require_permission("knowledge:write"))):
        return components.memory.create(
            principal, body.content, body.category, scope=body.scope, confidence=body.confidence,
            importance=body.importance, tags=body.tags, expires_at=body.expires_at,
        )

    @router.patch("/api/enterprise/memories/{memory_id}")
    def update_memory(memory_id: str, body: MemoryUpdateRequest, principal: Principal = Depends(require_permission("knowledge:write"))):
        changes = {key: value for key, value in body.model_dump().items() if value is not None}
        try:
            return components.memory.update(principal, memory_id, **changes)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.post("/api/enterprise/memories/{memory_id}/confirm")
    def confirm_memory(memory_id: str, principal: Principal = Depends(require_permission("knowledge:write"))):
        try:
            return components.memory.confirm(principal, memory_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.delete("/api/enterprise/memories/{memory_id}")
    def forget_memory(memory_id: str, principal: Principal = Depends(require_permission("knowledge:write"))):
        try:
            components.memory.forget(principal, memory_id)
            return {"ok": True}
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.post("/api/enterprise/documents")
    async def upload_document(file: UploadFile = File(...), scope: str = Form("company"), principal: Principal = Depends(require_permission("knowledge:write"))):
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
    def list_documents(principal: Principal = Depends(require_permission("knowledge:read"))):
        docs = components.documents.list(principal)
        for item in docs:
            row = components.db.one("SELECT COUNT(*) AS n FROM document_chunks WHERE document_id=? AND active=1 AND version=?", (item["id"], item["current_version"]))
            item["chunk_count"] = int(row["n"] if row else 0)
            item.pop("stored_path", None)
        return {"documents": docs}

    @router.post("/api/enterprise/documents/{document_id}/reindex")
    def reindex_document(document_id: str, principal: Principal = Depends(require_permission("knowledge:write"))):
        try:
            return components.documents.reindex(principal, document_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.delete("/api/enterprise/documents/{document_id}")
    def delete_document(document_id: str, principal: Principal = Depends(require_permission("knowledge:write"))):
        try:
            components.documents.delete(principal, document_id)
            return {"ok": True}
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc


    @router.post("/api/enterprise/semantic/resolve")
    def resolve_semantics(body: SemanticResolveRequest, principal: Principal = Depends(require_permission("analysis:run"))):
        return components.semantic.resolve(principal, body.columns, body.inferred_roles, on_date=body.on_date)

    @router.post("/api/enterprise/rules/{rule_id}/bind")
    def bind_analytic_rule(rule_id: str, body: RuleBindingRequest, principal: Principal = Depends(require_permission("knowledge:write"))):
        try:
            return components.analytics.bind_rule(principal, rule_id, rule_type=body.rule_type, target=body.target, priority=body.priority, scope=body.scope)
        except (ValueError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get("/api/enterprise/analytic-rules")
    def list_analytic_rules(principal: Principal = Depends(require_permission("analysis:run"))):
        return {"bindings": components.analytics.applicable_bindings(principal)}

    @router.get("/api/enterprise/datasets")
    def list_datasets(principal: Principal = Depends(require_permission("deliverable:read"))):
        datasets = components.datasets.list(principal)
        for item in datasets:
            item.pop("path", None)
        return {"datasets": datasets}

    @router.get("/api/enterprise/feedback")
    def list_feedback(limit: int = 100, principal: Principal = Depends(require_permission("knowledge:read"))):
        return {"feedback": components.feedback.list(principal, limit=limit)}

    @router.post("/api/enterprise/feedback")
    def submit_feedback(body: FeedbackRequest, principal: Principal = Depends(require_permission("knowledge:write"))):
        try:
            return components.feedback.submit(principal, **body.model_dump())
        except (ValueError, RuntimeError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/api/enterprise/feedback/{feedback_id}/validate")
    def validate_feedback(feedback_id: str, body: FeedbackDecisionRequest, principal: Principal = Depends(require_permission("knowledge:write"))):
        try:
            return components.feedback.validate_proposal(principal, feedback_id, replace_conflicts=body.replace_conflicts)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @router.post("/api/enterprise/feedback/{feedback_id}/reject")
    def reject_feedback(feedback_id: str, principal: Principal = Depends(require_permission("knowledge:write"))):
        try:
            return components.feedback.reject_proposal(principal, feedback_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @router.get("/api/enterprise/feedback/{feedback_id}/provenance")
    def feedback_provenance(feedback_id: str, principal: Principal = Depends(require_permission("knowledge:read"))):
        try:
            return components.feedback.provenance(principal, feedback_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.get("/api/enterprise/traces")
    def list_traces(limit: int = 100, principal: Principal = Depends(require_permission("admin:audit"))):
        return {"traces": components.traceability.list(principal, limit=limit)}

    @router.get("/api/enterprise/traces/{trace_id}")
    def get_trace(trace_id: str, principal: Principal = Depends(require_permission("admin:audit"))):
        try:
            return components.traceability.get(principal, trace_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.get("/api/enterprise/traces/{trace_id}/explain")
    def explain_trace(trace_id: str, principal: Principal = Depends(require_permission("admin:audit"))):
        try:
            return components.traceability.explain(principal, trace_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.get("/api/enterprise/admin/overview")
    def admin_overview(principal: Principal = Depends(require_permission("admin:audit"))):
        rules = components.governance.list_rules(principal, include_inactive=True) if hasattr(components, "governance") else []
        sem = components.governance.list_semantic_definitions(principal, include_inactive=True) if hasattr(components, "governance") else []
        feedback = components.feedback.list(principal, limit=500) if hasattr(components, "feedback") else []
        traces = components.traceability.list(principal, limit=500) if hasattr(components, "traceability") else []
        memories = components.memory.list(principal, include_inactive=True)
        docs = components.documents.list(principal)
        datasets = components.datasets.list(principal)
        statuses=[]
        for typ, rows in (("Regla", rules),("Definición", sem)):
            counts={}
            for row in rows: counts[row.get("status") or "N/D"]=counts.get(row.get("status") or "N/D",0)+1
            statuses.extend({"type":typ,"status":k,"count":v} for k,v in sorted(counts.items()))
        conflicts=0
        if hasattr(components,"governance"):
            for row in rules:
                if row.get("status") == "PROPUESTO": conflicts += len(components.governance.detect_rule_conflicts(principal,row["id"]))
            for row in sem:
                if row.get("status") == "PROPUESTO": conflicts += len(components.governance.detect_semantic_conflicts(principal,row["id"]))
        return {"counts":{"memories":len(memories),"documents":len(docs),"datasets":len(datasets),"rules":len(rules),"semantic_definitions":len(sem),"feedback_pending":sum(1 for x in feedback if x.get("proposal_status")=="PROPUESTO"),"traces":len(traces),"conflicts":conflicts},"statuses":statuses}

    @router.get("/api/enterprise/business-rules")
    def list_business_rules(status: Optional[str]=None, include_inactive: bool=False, principal: Principal=Depends(require_permission("knowledge:read"))):
        return {"items": components.governance.list_rules(principal,status=status,include_inactive=include_inactive)}

    @router.post("/api/enterprise/business-rules")
    def propose_business_rule(body: BusinessRuleCreateRequest, principal: Principal=Depends(require_permission("knowledge:write"))):
        return components.governance.propose_rule(principal,name=body.name,expression=body.expression,area=body.area,description=body.description,scope=body.scope,valid_from=body.valid_from,valid_to=body.valid_to,source_type="admin_console")

    @router.post("/api/enterprise/business-rules/{rule_id}/validate")
    def validate_business_rule(rule_id: str, body: GovernanceValidateRequest, principal: Principal=Depends(require_permission("knowledge:write"))):
        return components.governance.validate_rule(principal,rule_id,replace_conflicts=body.replace_conflicts)

    @router.post("/api/enterprise/business-rules/{rule_id}/reject")
    def reject_business_rule(rule_id: str, principal: Principal=Depends(require_permission("knowledge:write"))):
        return components.governance.reject_rule(principal,rule_id)

    @router.post("/api/enterprise/business-rules/{rule_id}/obsolete")
    def obsolete_business_rule(rule_id: str, principal: Principal=Depends(require_permission("knowledge:write"))):
        return components.governance.obsolete_rule(principal,rule_id)

    @router.get("/api/enterprise/semantic-definitions")
    def list_semantic_definitions(status: Optional[str]=None, include_inactive: bool=False, principal: Principal=Depends(require_permission("knowledge:read"))):
        return {"items": components.governance.list_semantic_definitions(principal,status=status,include_inactive=include_inactive)}

    @router.post("/api/enterprise/semantic-definitions")
    def propose_semantic_definition(body: SemanticDefinitionCreateRequest, principal: Principal=Depends(require_permission("knowledge:write"))):
        return components.governance.propose_semantic_definition(principal,physical_name=body.physical_name,semantic_name=body.semantic_name,data_type=body.data_type,unit=body.unit,area=body.area,description=body.description,scope=body.scope,valid_from=body.valid_from,valid_to=body.valid_to,source_type="admin_console")

    @router.post("/api/enterprise/semantic-definitions/{item_id}/validate")
    def validate_semantic_definition(item_id: str, body: GovernanceValidateRequest, principal: Principal=Depends(require_permission("knowledge:write"))):
        return components.governance.validate_semantic_definition(principal,item_id,replace_conflicts=body.replace_conflicts)

    @router.post("/api/enterprise/semantic-definitions/{item_id}/reject")
    def reject_semantic_definition(item_id: str, principal: Principal=Depends(require_permission("knowledge:write"))):
        return components.governance.reject_semantic_definition(principal,item_id)

    @router.get("/api/enterprise/analytic-rules")
    def list_analytic_rules(principal: Principal=Depends(require_permission("analysis:run"))):
        if not hasattr(components,"analytic_rules"): return {"items":[]}
        return {"items": components.analytic_rules.applicable_bindings(principal)}

    @router.post("/api/enterprise/rules/{rule_id}/bind")
    def bind_analytic_rule(rule_id: str, body: AnalyticBindRequest, principal: Principal=Depends(require_permission("knowledge:write"))):
        return components.analytic_rules.bind_rule(principal,rule_id,rule_type=body.rule_type,target=body.target,priority=body.priority,scope=body.scope)

    @router.get("/api/enterprise/knowledge/{object_type}/{object_id}/history")
    def knowledge_history(object_type: str, object_id: str, principal: Principal=Depends(require_permission("knowledge:read"))):
        if object_type not in {"business_rule","semantic_definition"}: raise HTTPException(status_code=400,detail="object_type no válido")
        try: return components.governance.provenance(principal,object_type,object_id)
        except KeyError as exc: raise HTTPException(status_code=404,detail=str(exc)) from exc

    @router.get("/api/enterprise/settings")
    def settings(principal: Principal = Depends(require_permission("config:read"))):
        return {
            "llm": components.cfg.section("llm"),
            "embeddings": components.cfg.section("embeddings"),
            "retrieval": components.cfg.section("retrieval"),
            "vector": {"backend_active": type(components.vectors).__name__, **components.cfg.section("vector")},
            "documents": components.cfg.section("documents"),
            "runtime": components.cfg.section("runtime"),
        }

    @router.put("/api/enterprise/settings")
    def update_settings(body: SettingsRequest, principal: Principal = Depends(require_permission("config:write"))):
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

    @router.get("/api/enterprise/performance")
    def enterprise_performance(principal: Principal = Depends(require_permission("admin:audit"))):
        from .performance import optional_engines
        return {
            "ok": True,
            "version": "8.5.5-r10.11-large-data",
            "engines": optional_engines(),
            "policy": {
                "large_csv": "streaming exacto por chunks",
                "profiling": "muestra controlada permitida",
                "business_metrics": "siempre exactas",
                "governed_rules": "fallback a evaluador completo para conservar semantica",
            },
        }

    @router.get("/api/enterprise/fine-tuning/runs")
    def finetune_runs(limit: int = 50, principal: Principal = Depends(require_permission("admin:audit"))):
        from .fine_tuning_dataset import FineTuningDatasetManager
        return {"runs": FineTuningDatasetManager(components.db, components.cfg.root).list_runs(principal, limit)}

    @router.post("/api/enterprise/fine-tuning/runs")
    def finetune_build(body: FineTuningBuildRequest, principal: Principal = Depends(require_permission("admin:audit"))):
        from .fine_tuning_dataset import FineTuningDatasetManager
        return FineTuningDatasetManager(components.db, components.cfg.root).build(principal)

    @router.get("/api/enterprise/fine-tuning/runs/{run_id}")
    def finetune_run(run_id: str, principal: Principal = Depends(require_permission("admin:audit"))):
        from .fine_tuning_dataset import FineTuningDatasetManager
        return FineTuningDatasetManager(components.db, components.cfg.root).get_run(principal, run_id)

    @router.post("/api/enterprise/fine-tuning/examples/{example_id}/decision")
    def finetune_decision(example_id: str, body: FineTuningDecisionRequest, principal: Principal = Depends(require_permission("admin:audit"))):
        from .fine_tuning_dataset import FineTuningDatasetManager
        try: return FineTuningDatasetManager(components.db, components.cfg.root).decide(principal, example_id, body.approve, body.reason)
        except (KeyError, ValueError) as exc: raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/api/enterprise/fine-tuning/runs/{run_id}/approve-safe")
    def finetune_approve_safe(run_id: str, principal: Principal = Depends(require_permission("admin:audit"))):
        from .fine_tuning_dataset import FineTuningDatasetManager
        return FineTuningDatasetManager(components.db, components.cfg.root).approve_all_safe(principal, run_id)

    @router.post("/api/enterprise/fine-tuning/runs/{run_id}/export")
    def finetune_export(run_id: str, body: FineTuningExportRequest, principal: Principal = Depends(require_permission("admin:audit"))):
        from .fine_tuning_dataset import FineTuningDatasetManager
        try: return FineTuningDatasetManager(components.db, components.cfg.root).export(principal, run_id, body.format)
        except (KeyError, ValueError) as exc: raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get("/api/enterprise/audit")
    def audit(limit: int = 100, principal: Principal = Depends(require_permission("admin:audit"))):
        rows = components.db.query(
            "SELECT * FROM audit_events WHERE company_id=? ORDER BY id DESC LIMIT ?",
            (principal.company_id, max(1, min(limit, 500))),
        )
        return {"events": [dict(row) for row in rows]}

    app.include_router(router)
    return components
