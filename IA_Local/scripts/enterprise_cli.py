from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from enterprise_ai.factory import build_components
from enterprise_ai.security import Principal, create_token, ensure_secret


def principal_from_args(args) -> Principal:
    return Principal(args.company, args.user, getattr(args, "role", "admin"))


def dump(value):
    print(json.dumps(value, ensure_ascii=False, indent=2, default=str))


def main() -> int:
    root_default = os.getenv("IA_LOCAL_ROOT") or ("C:/IA_Local" if os.name == "nt" else str(SCRIPT_DIR.parent))
    parser = argparse.ArgumentParser(description="Administracion IA Empresarial V8")
    parser.add_argument("--root", default=root_default)
    parser.add_argument("--company", default="empresa-local")
    parser.add_argument("--user", default="admin-local")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("mem-list")
    p = sub.add_parser("mem-add"); p.add_argument("content"); p.add_argument("--category", default="conocimiento_empresa"); p.add_argument("--scope", default="company")
    p = sub.add_parser("mem-search"); p.add_argument("query")
    p = sub.add_parser("mem-forget"); p.add_argument("id")
    p = sub.add_parser("mem-confirm"); p.add_argument("id")
    p = sub.add_parser("mem-update"); p.add_argument("id"); p.add_argument("content"); p.add_argument("--category")
    p = sub.add_parser("doc-index"); p.add_argument("path"); p.add_argument("--scope", default="company")
    sub.add_parser("doc-list")
    p = sub.add_parser("doc-reindex"); p.add_argument("id")
    p = sub.add_parser("doc-delete"); p.add_argument("id")
    p = sub.add_parser("token-create"); p.add_argument("--token-role", choices=["user", "admin"], default="user"); p.add_argument("--days", type=int, default=365)
    args = parser.parse_args()
    os.environ["IA_LOCAL_ROOT"] = str(Path(args.root).resolve())
    components = build_components(args.root)
    principal = principal_from_args(args)
    if args.cmd == "mem-list": dump(components.memory.list(principal, include_inactive=True))
    elif args.cmd == "mem-add": dump(components.memory.create(principal, args.content, args.category, scope=args.scope))
    elif args.cmd == "mem-search": dump(components.memory.search(principal, args.query))
    elif args.cmd == "mem-forget": components.memory.forget(principal, args.id); dump({"ok": True})
    elif args.cmd == "mem-confirm": dump(components.memory.confirm(principal, args.id))
    elif args.cmd == "mem-update":
        changes = {"content": args.content}
        if args.category: changes["category"] = args.category
        dump(components.memory.update(principal, args.id, **changes))
    elif args.cmd == "doc-index": dump(components.documents.index(principal, args.path, scope=args.scope))
    elif args.cmd == "doc-list": dump(components.documents.list(principal))
    elif args.cmd == "doc-reindex": dump(components.documents.reindex(principal, args.id))
    elif args.cmd == "doc-delete": components.documents.delete(principal, args.id); dump({"ok": True})
    elif args.cmd == "token-create":
        sec = components.cfg.section("security")
        secret = ensure_secret(sec["token_secret_file"])
        token_principal = Principal(args.company, args.user, args.token_role)
        print(create_token(secret, token_principal, args.days * 86400))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
