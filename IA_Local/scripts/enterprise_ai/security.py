from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,80}$")


@dataclass(frozen=True)
class Principal:
    company_id: str
    user_id: str
    role: str = "user"

    def __post_init__(self):
        if not _ID_RE.match(self.company_id) or not _ID_RE.match(self.user_id):
            raise ValueError("company_id/user_id contienen caracteres no permitidos")
        if self.role not in {"user", "admin"}:
            raise ValueError("Rol no valido")


def safe_component(value: str) -> str:
    value = Path(value or "archivo").name
    value = re.sub(r"[^A-Za-z0-9._ -]+", "_", value).strip(" .")
    return value[:160] or "archivo"


def safe_join(root: Path, *parts: str) -> Path:
    root = root.resolve()
    candidate = root.joinpath(*(safe_component(x) for x in parts)).resolve()
    if root != candidate and root not in candidate.parents:
        raise ValueError("Ruta fuera del directorio permitido")
    return candidate


def ensure_secret(path: str | Path) -> bytes:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    if not p.exists():
        p.write_text(secrets.token_urlsafe(64), encoding="ascii")
        try:
            os.chmod(p, 0o600)
        except Exception:
            pass
    return p.read_text(encoding="ascii").strip().encode("utf-8")


def _b64e(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64d(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def create_token(secret: bytes, principal: Principal, expires_seconds: Optional[int] = None) -> str:
    now = int(time.time())
    payload = {"company_id": principal.company_id, "user_id": principal.user_id, "role": principal.role, "iat": now}
    if expires_seconds:
        payload["exp"] = now + int(expires_seconds)
    body = _b64e(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    sig = _b64e(hmac.new(secret, body.encode("ascii"), hashlib.sha256).digest())
    return body + "." + sig


def verify_token(secret: bytes, token: str) -> Principal:
    try:
        body, sig = token.split(".", 1)
        expected = _b64e(hmac.new(secret, body.encode("ascii"), hashlib.sha256).digest())
        if not hmac.compare_digest(sig, expected):
            raise ValueError("Firma invalida")
        payload = json.loads(_b64d(body))
        if payload.get("exp") and int(payload["exp"]) < int(time.time()):
            raise ValueError("Token expirado")
        return Principal(str(payload["company_id"]), str(payload["user_id"]), str(payload.get("role", "user")))
    except Exception as exc:
        raise ValueError("Token de acceso invalido") from exc


def scope_clause(principal: Principal, alias: str = "") -> tuple[str, tuple[str, str]]:
    p = (alias + ".") if alias else ""
    return f"{p}company_id=? AND ({p}scope='company' OR {p}user_id=?)", (principal.company_id, principal.user_id)


PROMPT_INJECTION_PATTERNS = [
    r"ignore (all|any|the|previous).*instructions",
    r"ignora (todas|las|cualquier).*instrucciones",
    r"system prompt",
    r"developer message",
    r"you are now",
    r"act as system",
    r"reveal.*prompt",
    r"exfiltrat",
]


def detect_prompt_injection(text: str) -> bool:
    low = text or ""
    return any(re.search(pattern, low, flags=re.I | re.S) for pattern in PROMPT_INJECTION_PATTERNS)
