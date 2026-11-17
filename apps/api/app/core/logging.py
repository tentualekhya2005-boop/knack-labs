import json
import logging
import os
import re
import sys
from datetime import datetime, timezone
from typing import Any, Dict

SENSITIVE_PATTERNS = [
    re.compile(r"DO_NOT_LOG_ME_123", re.IGNORECASE),
    re.compile(r"(Bearer\s+)[A-Za-z0-9_\-\.]+", re.IGNORECASE),
    re.compile(
        r"(['\"]?(?:password|token|secret|api_key|access_token)['\"]?\s*[:=]\s*['\"])[^'\"]+(['\"])",
        re.IGNORECASE,
    ),
]

SENSITIVE_HEADERS = {
    "authorization",
    "x-api-key",
    "cookie",
    "set-cookie",
    "proxy-authorization",
}


def redact_text(text: str) -> str:
    if not isinstance(text, str):
        return text
    # Sanitize CRLF control characters to prevent Log Injection (CRLF log forging)
    sanitized = text.replace("\r", "\\r").replace("\n", "\\n")
    for pattern in SENSITIVE_PATTERNS:
        if "Bearer" in pattern.pattern:
            sanitized = pattern.sub(r"\1[REDACTED]", sanitized)
        elif "password" in pattern.pattern:
            sanitized = pattern.sub(r"\1[REDACTED]\2", sanitized)
        else:
            sanitized = pattern.sub("[REDACTED]", sanitized)
    return sanitized


def redact_data(data: Any) -> Any:
    if isinstance(data, str):
        return redact_text(data)
    elif isinstance(data, dict):
        sanitized = {}
        for k, v in data.items():
            if str(k).lower() in SENSITIVE_HEADERS:
                sanitized[k] = "[REDACTED]"
            else:
                sanitized[k] = redact_data(v)
        return sanitized
    elif isinstance(data, (list, tuple, set)):
        return [redact_data(item) for item in data]
    return data


class StructuredJsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_obj: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": redact_text(record.getMessage()),
        }

        # Include structured attributes if attached
        for field in (
            "request_id",
            "route",
            "method",
            "status_code",
            "latency_ms",
            "error_code",
            "client_ip",
        ):
            val = getattr(record, field, None)
            if val is not None:
                log_obj[field] = redact_data(val)

        if record.exc_info:
            tb_text = self.formatException(record.exc_info)
            log_obj["exception"] = redact_text(tb_text)

        return json.dumps(log_obj)


def setup_logger(name: str = "app") -> logging.Logger:
    app_logger = logging.getLogger(name)
    # Fixed Bug #3: Respect LOG_LEVEL from environment, defaulting to INFO
    env_level = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, env_level, logging.INFO)
    app_logger.setLevel(level)
    if not app_logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(StructuredJsonFormatter())
        app_logger.addHandler(handler)
        app_logger.propagate = False
    return app_logger


logger = setup_logger("app")

