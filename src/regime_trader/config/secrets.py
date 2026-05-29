from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

SENSITIVE_KEY_RE = re.compile(
    r"(secret|token|password|credential|account|api[_-]?key|authorization)",
    re.IGNORECASE,
)


class MissingSecretError(RuntimeError):
    pass


def load_secret(env_name: str, *, file_env_name: str | None = None, required: bool = True) -> str | None:
    value = os.getenv(env_name)
    if value:
        return value
    if file_env_name and (file_path := os.getenv(file_env_name)):
        secret = Path(file_path).read_text(encoding="utf-8").strip()
        if secret:
            return secret
    if required:
        raise MissingSecretError(f"missing required secret: {env_name}")
    return None


def redact_value(value: Any) -> str:
    text = str(value)
    if len(text) <= 4:
        return "***"
    return f"{text[:2]}***{text[-2:]}"


def redact_sensitive(payload: Any) -> Any:
    if isinstance(payload, dict):
        return {
            key: redact_value(value) if SENSITIVE_KEY_RE.search(str(key)) else redact_sensitive(value)
            for key, value in payload.items()
        }
    if isinstance(payload, list | tuple):
        return [redact_sensitive(value) for value in payload]
    return payload
