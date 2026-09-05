from __future__ import annotations
import hashlib, json, os, re, tempfile, time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional
from enterprise_tenant_registry import EnterpriseTenantRegistry, TenantRegistryError

CONFIG_VERSION="r10.20b.4"
DEFAULTS={"product_name":"IA Empresarial Local","default_locale":"es-MX","default_timezone":"America/Chihuahua","default_theme":"professional-light","default_ai_provider":"DISABLED","default_ai_model":None,"max_upload_mb":100,"default_sql_timeout":30,"default_sql_max_rows":500,"session_ttl_minutes":60,"enabled_features":{"sql_enabled":True,"knowledge_enabled":True,"pdf_enabled":True,"excel_enabled":True,"dashboard_enabled":True,"ai_enabled":False},"ai_provider":{"provider_id":"disabled","provider_type":"DISABLED","base_url":None,"model":None,"enabled":False,"timeout":30,"context_window":None}}
_GLOBAL=set(DEFAULTS); _TENANT={"display_name","locale","timezone","theme","ai_provider","ai_model","output_preferences","enabled_features","branding"}; _THEMES={"professional-light","professional-dark"}; _TYPES={"OLLAMA","OPENAI_COMPATIBLE_LOCAL","DISABLED"}; _MODEL=re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,159}$"); _COLOR=re.compile(r"^#[0-9A-Fa-f]{6}$")
class PlatformConfigError(ValueError):
 def __init__(self,code,message):super().__init__(message);self.code=code
def _canon(x):return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()
def _fp(x):return hashlib.sha256(_canon(x)).hexdigest()
def _now():return datetime.now(timezone.utc).isoformat()
def _safe_model(v):
 if v is not None and (not isinstance(v,str) or not _MODEL.fullmatch(v)):raise PlatformConfigError("AI_MODEL_INVALID","Modelo IA inválido")
 return v
def _provider(value):
 if not isinstance(value,dict) or set(value)-{"provider_id","provider_type","base_url","model","enabled","timeout","context_window"}:raise PlatformConfigError("AI_PROVIDER_INVALID","Provider IA inválido")
 typ=str(value.get("provider_type") or "").upper()
 if typ not in _TYPES:raise PlatformConfigError("AI_PROVIDER_INVALID","Provider IA inválido")
 out={"provider_id":str(value.get("provider_id") or typ.lower()),"provider_type":typ,"base_url":value.get("base_url"),"model":_safe_model(value.get("model")),"enabled":bool(value.get("enabled",typ!="DISABLED")),"timeout":int(value.get("timeout",30)),"context_window":value.get("context_window")}
 if out["timeout"]<1 or out["timeout"]>120:raise PlatformConfigError("AI_PROVIDER_INVALID","Timeout IA inválido")
 if typ=="DISABLED":out.update({"enabled":False,"base_url":None})
 elif not isinstance(out["base_url"],str) or not out["base_url"].startswith(("http://localhost","http://127.0.0.1")):raise PlatformConfigError("AI_PROVIDER_INVALID","URL IA local inválida")
 return out
def _branding(v):
 if not isinstance(v,dict) or set(v)-{"display_name","logo_reference","accent_color","theme"}:raise PlatformConfigError("BRANDING_INVALID","Branding inválido")
 out=dict(v)
 if "accent_color" in out and not _COLOR.fullmatch(str(out["accent_color"])):raise PlatformConfigError("BRANDING_INVALID","Color inválido")
 if "theme" in out and out["theme"] not in _THEMES:raise PlatformConfigError("BRANDING_INVALID","Theme inválido")
 ref=str(out.get("logo_reference") or "")
 if ref and (".." in ref or ref.startswith(("/","\\")) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,159}",ref)):raise PlatformConfigError("BRANDING_INVALID","Logo reference inválido")
 return out
class EnterprisePlatformConfigStore:
 def __init__(self,root:Path,tenant_registry:Optional[EnterpriseTenantRegistry]=None):self.root=Path(root);self.path=self.root/"platform_config.json";self.tenants=tenant_registry
 def _tenant_key(self,tenant_id):
  return self.tenants.assert_active(tenant_id)["tenant_id"] if self.tenants else str(tenant_id)
 def _load(self):
  if not self.path.exists():return {"schema_version":CONFIG_VERSION,"global":dict(DEFAULTS),"tenants":{},"audit":[]}
  try:d=json.loads(self.path.read_text(encoding="utf8"))
  except Exception as e:raise PlatformConfigError("CONFIG_INTEGRITY_MISMATCH","Config ilegible") from e
  sig=d.pop("fingerprint_sha256",None)
  if d.get("schema_version")!=CONFIG_VERSION or sig!=_fp(d):raise PlatformConfigError("CONFIG_INTEGRITY_MISMATCH","Config alterada")
  return d
 def _save(self,d):
  self.root.mkdir(parents=True,exist_ok=True);d["fingerprint_sha256"]=_fp({k:v for k,v in d.items() if k!="fingerprint_sha256"});h=tempfile.NamedTemporaryFile("w",encoding="utf8",dir=self.root,delete=False)
  try:
   with h:json.dump(d,h,ensure_ascii=False,separators=(",",":"))
   os.replace(h.name,self.path)
  finally:
   if os.path.exists(h.name):os.unlink(h.name)
 def _event(self,d,event,tenant_id=None):d["audit"].append({"event":event,"tenant_id":tenant_id,"at":_now()})
 def global_config(self):return dict(self._load()["global"])
 def update_global(self,changes):
  if not isinstance(changes,dict) or set(changes)-_GLOBAL:raise PlatformConfigError("CONFIG_INVALID","Campos globales inválidos")
  d=self._load();g=d["global"]
  for k,v in changes.items():
   if k=="ai_provider":v=_provider(v)
   if k=="default_ai_model":v=_safe_model(v)
   if k=="default_theme" and v not in _THEMES:raise PlatformConfigError("CONFIG_INVALID","Theme inválido")
   if k=="enabled_features" and (not isinstance(v,dict) or set(v)-set(DEFAULTS["enabled_features"])):raise PlatformConfigError("CONFIG_INVALID","Features inválidas")
   if "secret" in k or "password" in k or "token" in k:raise PlatformConfigError("CONFIG_INVALID","Secret no permitido")
   g[k]=v
  self._event(d,"PLATFORM_CONFIG_UPDATED");self._save(d);return dict(g)
 def tenant_config(self,tenant_id):
  key=self._tenant_key(tenant_id);d=self._load();legacy=[k for k in d["tenants"] if k.lower()==key.lower() and k!=key]
  if key in d["tenants"] and legacy:raise PlatformConfigError("CONFIG_INTEGRITY_MISMATCH","Configuración tenant duplicada")
  if len(legacy)>1:raise PlatformConfigError("CONFIG_INTEGRITY_MISMATCH","Configuración tenant ambigua")
  return dict(d["tenants"].get(key,d["tenants"].get(legacy[0],{}) if legacy else {}))
 def update_tenant(self,tenant_id,changes):
  key=self._tenant_key(tenant_id)
  if not isinstance(changes,dict) or set(changes)-_TENANT:raise PlatformConfigError("CONFIG_INVALID","Campos tenant inválidos")
  d=self._load();legacy=[k for k in d["tenants"] if k.lower()==key.lower() and k!=key]
  if key in d["tenants"] and legacy or len(legacy)>1:raise PlatformConfigError("CONFIG_INTEGRITY_MISMATCH","Configuración tenant duplicada")
  current=dict(d["tenants"].pop(legacy[0],{}) if legacy else d["tenants"].get(key,{}))
  for k,v in changes.items():
   if k=="branding":v=_branding(v)
   if k=="theme" and v not in _THEMES:raise PlatformConfigError("CONFIG_INVALID","Theme inválido")
   if k=="ai_provider":v=_provider(v)
   if k=="ai_model":v=_safe_model(v)
   if k=="enabled_features" and (not isinstance(v,dict) or set(v)-set(DEFAULTS["enabled_features"])):raise PlatformConfigError("CONFIG_INVALID","Features inválidas")
   current[k]=v
  d["tenants"][key]=current;self._event(d,"TENANT_CONFIG_UPDATED",key);
  if "branding" in changes:self._event(d,"BRANDING_UPDATED",key)
  if "ai_provider" in changes:self._event(d,"AI_PROVIDER_UPDATED",key)
  self._save(d);return dict(current)
 def resolve_effective_config(self,tenant_id=None,runtime_override=None):
  g=self.global_config();t=self.tenant_config(tenant_id) if tenant_id else {};out=dict(g);out.update({k:v for k,v in t.items() if k not in {"branding","enabled_features"}});out["enabled_features"]={**g["enabled_features"],**t.get("enabled_features",{})};out["branding"]={"display_name":t.get("display_name") or g["product_name"],"theme":t.get("theme") or g["default_theme"],**t.get("branding",{})}
  if runtime_override:out.update({k:v for k,v in runtime_override.items() if k in {"locale","timezone","theme"}})
  return out
 def public_effective_config(self,tenant_id=None):
  c=self.resolve_effective_config(tenant_id);return {"product_name":c["product_name"],"display_name":c["branding"]["display_name"] or "IA Empresarial Local","locale":c.get("locale",c["default_locale"]),"timezone":c.get("timezone",c["default_timezone"]),"theme":c["branding"].get("theme",c["default_theme"]),"accent_color":c["branding"].get("accent_color"),"logo_reference":c["branding"].get("logo_reference"),"enabled_features":c["enabled_features"],"ai_available":bool(c.get("ai_provider",g if False else {}).get("enabled",False)) if isinstance(c.get("ai_provider"),dict) else False}
 def design_context(self,tenant_id=None):
  from enterprise_design_system import get_design_tokens
  public=self.public_effective_config(tenant_id);tokens=get_design_tokens(public["theme"])
  if public["accent_color"]:tokens["colors"]["accent"]=public["accent_color"]
  return {"display_name":public["display_name"],"theme":public["theme"],"tokens":tokens}
 def test_provider(self,config,adapter=None):
  p=_provider(config);start=time.monotonic()
  if p["provider_type"]=="DISABLED":return {"status":"DISABLED","latency_ms":0.0}
  try:
   if not adapter:raise PlatformConfigError("AI_PROVIDER_UNAVAILABLE","Provider IA no disponible")
   adapter.health(p);return {"status":"PASS","latency_ms":round((time.monotonic()-start)*1000,3),"provider_type":p["provider_type"]}
  except PlatformConfigError:raise
  except Exception as e:raise PlatformConfigError("AI_PROVIDER_UNAVAILABLE","Provider IA no disponible") from e
