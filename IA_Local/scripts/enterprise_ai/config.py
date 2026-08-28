from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def default_config(root: Path) -> Dict[str, Any]:
    return {
        "version": "8.5.5",
        "root": str(root),
        "database_path": str(root / "data" / "enterprise" / "enterprise_ai.sqlite3"),
        "knowledge_dir": str(root / "workspace" / "Conocimiento"),
        "vector": {
            "backend": "qdrant",
            "qdrant_path": str(root / "data" / "enterprise" / "qdrant"),
            "sqlite_path": str(root / "data" / "enterprise" / "vectors.sqlite3"),
            "fallback_to_sqlite": True,
        },
        "llm": {
            "provider": "ollama",
            "ollama_url": "http://127.0.0.1:11434",
            "ollama_model": "qwen3:4b-instruct",
            "lmstudio_url": "http://127.0.0.1:1234/v1",
            "lmstudio_model": "qwen3-4b-instruct-2507",
            "timeout_seconds": 600,
            "temperature": 0.2,
            "generation_mode": "natural",
            "max_tokens": 0,
            "num_ctx": 4096,
            "detailed_num_ctx": 16384,
        },
        "embeddings": {
            "provider": "ollama",
            "model": "nomic-embed-text",
            "ollama_url": "http://127.0.0.1:11434",
            "lmstudio_url": "http://127.0.0.1:1234/v1",
            "lmstudio_model": "text-embedding-model",
            "timeout_seconds": 180,
        },
        "retrieval": {
            "max_memories": 6,
            "max_document_chunks": 8,
            "max_context_chars": 18000,
            "memory_min_score": 0.20,
            "document_min_score": 0.18,
        },
        "documents": {
            "max_file_mb": 250,
            "chunk_chars": 1200,
            "chunk_overlap": 180,
            "tabular_preview_rows": 300,
            "allowed_extensions": [".pdf", ".xlsx", ".xls", ".xlsm", ".xlsb", ".csv", ".docx", ".txt", ".md", ".markdown"],
        },
        "security": {
            "token_secret_file": str(root / "config" / "enterprise.secret"),
            "local_token_file": str(root / "config" / "local-user.token"),
            "default_company": "empresa-local",
            "default_user": "admin-local",
            "bind_local_only": True,
        },
        "runtime": {
            "max_concurrent_generations": 1,
            "queue_timeout_seconds": 120,
            "open_terminal_enabled": False,
            "warmup_llm": True,
            "keep_alive": "30m",
            "max_generation_seconds": 900,
            "max_auto_continuations": 2,
        },
        "observability": {
            "log_file": str(root / "logs" / "enterprise_ai.log"),
            "store_prompt_text": False,
            "max_log_mb": 5,
            "backup_count": 5,
        },
    }


@dataclass
class EnterpriseConfig:
    root: Path
    raw: Dict[str, Any] = field(default_factory=dict)

    @property
    def database_path(self) -> Path:
        return Path(self.raw["database_path"])

    @property
    def knowledge_dir(self) -> Path:
        return Path(self.raw["knowledge_dir"])

    def section(self, name: str) -> Dict[str, Any]:
        return dict(self.raw.get(name, {}))

    def ensure_dirs(self) -> None:
        paths = [
            self.database_path.parent,
            self.knowledge_dir,
            Path(self.raw["vector"]["sqlite_path"]).parent,
            Path(self.raw["observability"]["log_file"]).parent,
            self.root / "config",
        ]
        for path in paths:
            path.mkdir(parents=True, exist_ok=True)


def load_config(root: str | Path | None = None) -> EnterpriseConfig:
    env_root = os.getenv("IA_LOCAL_ROOT")
    default_root = Path("C:/IA_Local") if os.name == "nt" else Path.cwd()
    resolved_root = Path(root or env_root or default_root).resolve()
    merged = default_config(resolved_root)
    cfg_path = Path(os.getenv("IA_ENTERPRISE_CONFIG", str(resolved_root / "config" / "enterprise_ai.json")))
    if cfg_path.exists():
        try:
            merged = _deep_merge(merged, json.loads(cfg_path.read_text(encoding="utf-8-sig")))
        except Exception:
            pass
    if os.getenv("OLLAMA_URL"):
        merged["llm"]["ollama_url"] = os.getenv("OLLAMA_URL")
        merged["embeddings"]["ollama_url"] = os.getenv("OLLAMA_URL")
    if os.getenv("OLLAMA_MODEL"):
        merged["llm"]["ollama_model"] = os.getenv("OLLAMA_MODEL")
    if os.getenv("IA_LLM_PROVIDER"):
        merged["llm"]["provider"] = os.getenv("IA_LLM_PROVIDER")
    cfg = EnterpriseConfig(resolved_root, merged)
    cfg.ensure_dirs()
    return cfg


def write_default_config(root: str | Path, overwrite: bool = False) -> Path:
    root = Path(root).resolve()
    path = root / "config" / "enterprise_ai.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    if overwrite or not path.exists():
        path.write_text(json.dumps(default_config(root), ensure_ascii=False, indent=2), encoding="utf-8")
    return path
