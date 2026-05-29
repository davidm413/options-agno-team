from __future__ import annotations

from enum import StrEnum
from typing import ClassVar

from regime_trader.schemas.base import StrictModel


class ToolPermission(StrEnum):
    READ_MARKET = "read_market"
    READ_ACCOUNT = "read_account"
    RISK = "risk"
    PREFLIGHT = "preflight"
    EXECUTE = "execute"
    RETRAIN = "retrain"
    MEMORY_MUTATE = "memory_mutate"


class AuthorizationContext(StrictModel):
    caller_id: str
    permissions: tuple[ToolPermission, ...] = ()


class AuthorizationPolicy:
    REQUIRED: ClassVar[dict[str, tuple[ToolPermission, ...]]] = {
        "detect_regime": (ToolPermission.READ_MARKET,),
        "compare_regimes": (ToolPermission.READ_MARKET,),
        "scan_market": (ToolPermission.READ_MARKET,),
        "propose_options_strategy": (ToolPermission.READ_MARKET,),
        "check_portfolio_risk": (ToolPermission.READ_ACCOUNT, ToolPermission.RISK),
        "execute_trade": (ToolPermission.EXECUTE, ToolPermission.PREFLIGHT),
        "get_live_monitoring": (ToolPermission.READ_MARKET, ToolPermission.READ_ACCOUNT),
        "retrain_clusters": (ToolPermission.RETRAIN,),
        "reflect_on_trade": (ToolPermission.MEMORY_MUTATE,),
    }

    def authorize(self, tool_name: str, context: AuthorizationContext) -> tuple[bool, tuple[str, ...]]:
        required = self.REQUIRED.get(tool_name, ())
        missing = tuple(permission for permission in required if permission not in context.permissions)
        return not missing, tuple(str(permission) for permission in missing)
