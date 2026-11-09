from __future__ import annotations

import re
from typing import Any

REDACTED = "<redacted>"
SECRET_KEY = re.compile(r"(?i)(passw(or)?d|passphrase|secret|token|api_?key|private|(^|_)pat$)")


def is_secret_key(key: str) -> bool:
    return bool(SECRET_KEY.search(key))


def redact(value: Any) -> Any:
    """Recursively blank out values whose key looks secret, and any vaulted blob."""
    if isinstance(value, dict):
        return {k: REDACTED if is_secret_key(str(k)) else redact(v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v) for v in value]
    if isinstance(value, str) and value.lstrip().startswith("$ANSIBLE_VAULT"):
        return REDACTED
    return value
