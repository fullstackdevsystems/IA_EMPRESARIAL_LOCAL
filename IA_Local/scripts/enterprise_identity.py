from __future__ import annotations
import hashlib, json, os, re, secrets, tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from enterprise_tenant_registry import EnterpriseTenantRegistry, TenantRegistryError

IDENTITY_VERSION="r10.20b.2"
ROLES={"SYSTEM_ADMIN","TENANT_ADMIN","ANALYST","VIEWER"}
PERMISSIONS={"SYSTEM_ADMIN":{"*"},"TENANT_ADMIN":{"tenant:list","tenant:update","user:list","user:create","user:update","user:disable","user:role_assign","analysis:run","knowledge:read","knowledge:write","sql:read","sql:configure","deliverable:read","admin:audit"},"ANALYST":{"analysis:run","knowledge:read","knowledge:write","sql:read","deliverable:read"},"VIEWER":{"knowledge:read","deliverable:read"}}
_ID=re.compile(r"^[a-z0-9][a-z0-9_.-]{0,79}$")
class IdentityError(ValueError):
 def __init__(self,code,message): super().__init__(message); self.code=code
def _now(): return datetime.now(timezone.utc)
def _canon(x): return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()
def _fp(x): return hashlib.sha256(_canon(x)).hexdigest()
def _id(x,field):
 x=str(x or "").strip().lower()
 if not _ID.fullmatch(x): raise IdentityError("USER_INVALID_ID",f"{field} inválido")
 return x
def _password(password):
 if not isinstance(password,str) or len(password)<12: raise IdentityError("PASSWORD_INVALID","Password debe tener al menos 12 caracteres")
 salt=secrets.token_bytes(16); key=hashlib.scrypt(password.encode(),salt=salt,n=2**14,r=8,p=1)
 return "scrypt$16384$8$1$"+salt.hex()+"$"+key.hex()
def _verify(password,stored):
 try:
  _,n,r,p,salt,key=stored.split("$"); got=hashlib.scrypt(password.encode(),salt=bytes.fromhex(salt),n=int(n),r=int(r),p=int(p)); return secrets.compare_digest(got.hex(),key)
 except Exception:return False
def _public(u): return {k:v for k,v in u.items() if k not in {"password_hash","integrity"}}
class EnterpriseIdentityStore:
 def __init__(self,root:Path,tenant_registry:EnterpriseTenantRegistry,ttl_minutes:int=60,lock_attempts:int=5): self.root=Path(root);self.tenants=tenant_registry;self.path=self.root/"identity.json";self.ttl=ttl_minutes;self.lock_attempts=lock_attempts
 def _load(self):
  if not self.path.exists(): return {"version":IDENTITY_VERSION,"users":[],"sessions":[],"audit":[]}
  try:d=json.loads(self.path.read_text(encoding="utf8"))
  except Exception as e: raise IdentityError("IDENTITY_INTEGRITY_MISMATCH","Identity store ilegible") from e
  sig=d.pop("fingerprint_sha256",None)
  if d.get("version")!=IDENTITY_VERSION or sig!=_fp(d): raise IdentityError("IDENTITY_INTEGRITY_MISMATCH","Identity store alterado")
  return d
 def _save(self,d):
  self.root.mkdir(parents=True,exist_ok=True); d["fingerprint_sha256"]=_fp({k:v for k,v in d.items() if k!="fingerprint_sha256"}); f=tempfile.NamedTemporaryFile("w",encoding="utf8",dir=self.root,delete=False)
  try:
   with f: json.dump(d,f,ensure_ascii=False,separators=(",",":"))
   os.replace(f.name,self.path)
  finally:
   if os.path.exists(f.name): os.unlink(f.name)
 def _event(self,d,event,user_id=None): d["audit"].append({"event":event,"user_id":user_id,"at":_now().isoformat()})
 def bootstrap_admin(self,*,user_id,username,display_name,password,tenant_id):
  d=self._load()
  if any("SYSTEM_ADMIN" in u["roles"] and u["status"]=="ACTIVE" for u in d["users"]): raise IdentityError("BOOTSTRAP_ALREADY_COMPLETE","Ya existe SYSTEM_ADMIN")
  return self.create_user(user_id=user_id,username=username,display_name=display_name,password=password,tenant_id=tenant_id,roles=["SYSTEM_ADMIN"])
 def create_user(self,*,user_id,username,display_name,password,tenant_id,roles, business_units=None, branches=None):
  d=self._load(); uid=_id(user_id,"user_id"); uname=_id(username,"username"); self.tenants.assert_active(tenant_id)
  if any(u["user_id"]==uid or u["username"]==uname for u in d["users"]): raise IdentityError("USER_ALREADY_EXISTS","Usuario ya existe")
  roles=set(roles or []);
  if not roles or not roles<=ROLES: raise IdentityError("ROLE_INVALID","Rol inválido")
  now=_now().isoformat();u={"user_id":uid,"username":uname,"display_name":str(display_name or "").strip(),"tenant_id":str(tenant_id),"status":"ACTIVE","roles":sorted(roles),"business_units":list(business_units or []),"branches":list(branches or []),"password_hash":_password(password),"failed_attempts":0,"locked_until":None,"created_at":now,"updated_at":now};d["users"].append(u);self._event(d,"USER_CREATED",uid);self._save(d);return _public(u)
 def get(self,user_id):
  uid=_id(user_id,"user_id");u=next((x for x in self._load()["users"] if x["user_id"]==uid),None)
  if not u: raise IdentityError("USER_NOT_FOUND","Usuario no encontrado")
  return _public(u)
 def list(self,tenant_id=None):
  return [_public(u) for u in self._load()["users"] if tenant_id is None or u["tenant_id"]==tenant_id]
 def _find(self,d,uid):
  u=next((x for x in d["users"] if x["user_id"]==_id(uid,"user_id")),None)
  if not u: raise IdentityError("USER_NOT_FOUND","Usuario no encontrado")
  return u
 def update(self,user_id,**changes):
  d=self._load();u=self._find(d,user_id)
  for k in ("display_name","business_units","branches"):
   if k in changes:u[k]=changes[k]
  if "roles" in changes:
   roles=set(changes["roles"] or []);
   if not roles or not roles<=ROLES: raise IdentityError("ROLE_INVALID","Rol inválido")
   u["roles"]=sorted(roles);self._event(d,"ROLE_CHANGED",u["user_id"])
  u["updated_at"]=_now().isoformat();self._event(d,"USER_UPDATED",u["user_id"]);self._save(d);return _public(u)
 def set_status(self,user_id,status):
  d=self._load();u=self._find(d,user_id)
  if status=="DISABLED" and "SYSTEM_ADMIN" in u["roles"] and u["status"]=="ACTIVE" and sum("SYSTEM_ADMIN" in x["roles"] and x["status"]=="ACTIVE" for x in d["users"])<=1: raise IdentityError("LAST_SYSTEM_ADMIN","No se puede deshabilitar último SYSTEM_ADMIN")
  u["status"]=status;u["updated_at"]=_now().isoformat()
  if status=="DISABLED": self._revoke(d,u["user_id"]);self._event(d,"USER_DISABLED",u["user_id"])
  else:self._event(d,"USER_ENABLED",u["user_id"])
  self._save(d);return _public(u)
 def _revoke(self,d,uid):
  for s in d["sessions"]:
   if s["user_id"]==uid:s["revoked"]=True
 def login(self,username,password):
  d=self._load();u=next((x for x in d["users"] if x["username"]==str(username or "").strip().lower()),None);now=_now()
  if not u or u["status"]!="ACTIVE": self._event(d,"LOGIN_FAILED",None);self._save(d);raise IdentityError("AUTH_INVALID_CREDENTIALS","Credenciales inválidas")
  if u.get("locked_until") and now<datetime.fromisoformat(u["locked_until"]): raise IdentityError("AUTH_LOCKED","Acceso temporalmente bloqueado")
  if not self.tenants.assert_active(u["tenant_id"]): raise IdentityError("AUTH_INVALID_CREDENTIALS","Credenciales inválidas")
  if not _verify(password,u["password_hash"]):
   u["failed_attempts"]=int(u.get("failed_attempts",0))+1
   if u["failed_attempts"]>=self.lock_attempts:u["locked_until"]=(now+timedelta(minutes=5)).isoformat()
   self._event(d,"LOGIN_FAILED",u["user_id"]);self._save(d);raise IdentityError("AUTH_INVALID_CREDENTIALS","Credenciales inválidas")
  u["failed_attempts"]=0;u["locked_until"]=None;token=secrets.token_urlsafe(32);d["sessions"].append({"token_fingerprint":hashlib.sha256(token.encode()).hexdigest(),"user_id":u["user_id"],"created_at":now.isoformat(),"expires_at":(now+timedelta(minutes=self.ttl)).isoformat(),"revoked":False});self._event(d,"LOGIN_SUCCESS",u["user_id"]);self._save(d);return token,_public(u)
 def authenticate(self,token):
  d=self._load();fp=hashlib.sha256(str(token or "").encode()).hexdigest();s=next((x for x in d["sessions"] if x["token_fingerprint"]==fp),None)
  if not s or s["revoked"]: raise IdentityError("AUTH_SESSION_INVALID","Sesión inválida")
  if _now()>datetime.fromisoformat(s["expires_at"]): raise IdentityError("AUTH_SESSION_EXPIRED","Sesión expirada")
  u=self._find(d,s["user_id"])
  if u["status"]!="ACTIVE":raise IdentityError("USER_DISABLED","Usuario deshabilitado")
  self.tenants.assert_active(u["tenant_id"]);return _public(u)
 def logout(self,token):
  d=self._load();fp=hashlib.sha256(str(token or "").encode()).hexdigest();s=next((x for x in d["sessions"] if x["token_fingerprint"]==fp),None)
  if not s:raise IdentityError("AUTH_SESSION_INVALID","Sesión inválida")
  s["revoked"]=True;self._event(d,"LOGOUT",s["user_id"]);self._save(d)
 def change_password(self,user_id,password):
  d=self._load();u=self._find(d,user_id);u["password_hash"]=_password(password);u["updated_at"]=_now().isoformat();self._revoke(d,u["user_id"]);self._event(d,"PASSWORD_CHANGED",u["user_id"]);self._save(d)
 def has_permission(self,user,permission): return "*" in set().union(*(PERMISSIONS.get(r,set()) for r in user["roles"])) or permission in set().union(*(PERMISSIONS.get(r,set()) for r in user["roles"]))
 def scope(self,user, business_unit=None, branch=None):
  if business_unit and user["business_units"] and business_unit not in user["business_units"]:raise IdentityError("BUSINESS_UNIT_SCOPE_DENIED","Unidad no permitida")
  if branch and user["branches"] and branch not in user["branches"]:raise IdentityError("BRANCH_SCOPE_DENIED","Sucursal no permitida")
  return {"company_id":user["tenant_id"],"user_id":user["user_id"],"business_unit":business_unit,"branch":branch}
