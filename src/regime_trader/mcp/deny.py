from __future__ import annotations

DENIED_CAPABILITIES = (
    "shell",
    "python",
    "sql",
    "http",
    "credential",
    "secret",
    "raw_order",
)


def deny_arbitrary_capability(request: str) -> tuple[bool, str | None]:
    lowered = request.lower()
    for capability in DENIED_CAPABILITIES:
        if capability in lowered:
            return True, f"unsupported_arbitrary_{capability}_request"
    return False, None
