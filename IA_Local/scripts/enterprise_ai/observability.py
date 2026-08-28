from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Dict


class JsonLineFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key in ("event", "request_id", "company_id", "user_id", "route", "error_type"):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        return json.dumps(payload, ensure_ascii=False)


def _close_handler(logger: logging.Logger, handler: logging.Handler) -> None:
    """Retira y cierra un handler sin dejar el archivo bloqueado en Windows."""
    try:
        handler.flush()
    except Exception:
        pass
    try:
        logger.removeHandler(handler)
    except Exception:
        pass
    try:
        handler.close()
    except Exception:
        pass


def shutdown_logging(log_path: str | Path | None = None) -> None:
    """Cierra handlers administrados por IA Local.

    Si ``log_path`` se proporciona, solo cierra el handler de ese archivo.
    Sin ruta, cierra todos los handlers administrados del logger ``enterprise_ai``.
    Esto es importante en Windows, donde un RotatingFileHandler abierto impide
    eliminar directorios temporales durante los gates de prueba.
    """
    logger = logging.getLogger("enterprise_ai")
    marker = str(Path(log_path).resolve()) if log_path is not None else None
    for handler in list(logger.handlers):
        managed_path = getattr(handler, "_ia_log_path", None)
        if managed_path is None:
            continue
        if marker is None or managed_path == marker:
            _close_handler(logger, handler)


def configure_logging(cfg) -> logging.Logger:
    obs = cfg.section("observability")
    path = Path(obs.get("log_file") or (cfg.root / "logs" / "enterprise_ai.log"))
    path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("enterprise_ai")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    marker = str(path.resolve())

    # El logger de Python es global. En tests/rebuilds se crean distintas raíces
    # dentro del mismo proceso; cualquier handler administrado que apunte a otra
    # raíz debe cerrarse antes de abrir el nuevo para no bloquear archivos en Windows.
    for handler in list(logger.handlers):
        managed_path = getattr(handler, "_ia_log_path", None)
        if managed_path == marker:
            return logger
        if managed_path is not None:
            _close_handler(logger, handler)

    handler = RotatingFileHandler(
        path,
        maxBytes=max(1, int(obs.get("max_log_mb", 5))) * 1024 * 1024,
        backupCount=max(1, int(obs.get("backup_count", 5))),
        encoding="utf-8",
        delay=True,
    )
    handler._ia_log_path = marker  # type: ignore[attr-defined]
    handler.setFormatter(JsonLineFormatter())
    logger.addHandler(handler)
    logger.info("enterprise_ai logging initialized", extra={"event": "logging.init"})
    return logger
