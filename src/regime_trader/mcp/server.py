from __future__ import annotations

from typing import Any

from regime_trader.mcp.auth import AuthorizationContext, AuthorizationPolicy
from regime_trader.mcp.deny import deny_arbitrary_capability
from regime_trader.persistence.audit import AuditLogger


class ToolDeniedError(PermissionError):
    pass


class TradingToolService:
    def __init__(self, *, audit: AuditLogger | None = None, policy: AuthorizationPolicy | None = None) -> None:
        self.audit = audit or AuditLogger()
        self.policy = policy or AuthorizationPolicy()

    def validate_authorized(self, tool_name: str, context: AuthorizationContext, payload: dict[str, Any]) -> None:
        denied, reason = deny_arbitrary_capability(str(payload))
        if denied:
            self.audit.record("capability_denied", payload={"tool": tool_name, "reason": reason})
            raise ToolDeniedError(reason or "capability_denied")
        allowed, missing = self.policy.authorize(tool_name, context)
        if not allowed:
            self.audit.record(
                "authorization_failed",
                payload={"tool": tool_name, "caller_id": context.caller_id, "missing": missing},
            )
            raise ToolDeniedError(f"missing permissions: {', '.join(missing)}")
        self.audit.record("tool_authorized", payload={"tool": tool_name, "caller_id": context.caller_id})


def build_mcp_server(tool_service: TradingToolService | None = None) -> Any:
    service = tool_service or TradingToolService()
    from mcp.server.fastmcp import FastMCP

    server: Any = FastMCP("regime-trader")

    @server.tool()  # type: ignore[untyped-decorator]
    def deny_unsupported_request(request: str) -> dict[str, Any]:
        denied, reason = deny_arbitrary_capability(request)
        if denied:
            service.audit.record("capability_denied", payload={"request": request, "reason": reason})
            return {"status": "denied", "reason": reason}
        return {"status": "unsupported", "reason": "use typed trading tools only"}

    return server
