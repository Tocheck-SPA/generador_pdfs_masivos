"""Logging estructurado en JSON. Nunca registra datos sensibles ni URLs firmadas."""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone

_SENSITIVE_KEYS = {"rut", "email", "signed_url", "presigned_url", "password", "secret", "api_key"}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname.lower(),
            "logger": record.name,
            "message": record.getMessage(),
        }
        extra = getattr(record, "context", None)
        if isinstance(extra, dict):
            for key, value in extra.items():
                if key.lower() in _SENSITIVE_KEYS:
                    continue
                payload[key] = value
        if record.exc_info:
            payload["error"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def log_context(logger: logging.Logger, level: int, message: str, **context: object) -> None:
    """Emite un log con contexto estructurado, filtrando claves sensibles."""
    logger.log(level, message, extra={"context": context})
