from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from enterprise_ai.config import load_config, write_default_config
from enterprise_ai.database import Database
from enterprise_ai.security import Principal, create_token, ensure_secret
from enterprise_ai.vector_store import build_vector_store


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=os.getenv("IA_LOCAL_ROOT") or ("C:/IA_Local" if os.name == "nt" else str(SCRIPT_DIR.parent)))
    parser.add_argument("--pull-models", action="store_true")
    parser.add_argument("--force-token", action="store_true")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    os.environ["IA_LOCAL_ROOT"] = str(root)
    cfg_path = write_default_config(root)
    cfg = load_config(root)
    Database(cfg.database_path)
    vector_store = build_vector_store(cfg.section("vector"))
    sec_cfg = cfg.section("security")
    secret = ensure_secret(sec_cfg["token_secret_file"])
    token_path = Path(sec_cfg["local_token_file"])
    if args.force_token or not token_path.exists():
        principal = Principal(sec_cfg.get("default_company", "empresa-local"), sec_cfg.get("default_user", "admin-local"), "admin")
        token = create_token(secret, principal, expires_seconds=60 * 60 * 24 * 365 * 10)
        token_path.write_text(token, encoding="ascii")
    if args.pull_models:
        for model in [cfg.section("llm").get("ollama_model", "qwen3:4b-instruct"), cfg.section("embeddings").get("model", "nomic-embed-text")]:
            try:
                subprocess.run(["ollama", "pull", model], check=False)
            except Exception as exc:
                print(f"ADVERTENCIA: no se pudo ejecutar ollama pull {model}: {exc}")
    print(json.dumps({
        "ok": True,
        "version": "8.5.5",
        "config": str(cfg_path),
        "database": str(cfg.database_path),
        "vector_store": type(vector_store).__name__,
        "token_file": str(token_path),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
