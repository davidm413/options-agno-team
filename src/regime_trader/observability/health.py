from __future__ import annotations

from pydantic import Field

from regime_trader.config.models import AppConfig
from regime_trader.schemas.base import StrictModel


class HealthResult(StrictModel):
    status: str
    checks: dict[str, str] = Field(default_factory=dict)


def readiness_check(config: AppConfig) -> HealthResult:
    checks: dict[str, str] = {
        "provider_config": "configured" if config.provider.name else "missing",
        "execution_mode": config.execution.mode,
        "live_trading": "enabled" if config.execution.live_trading_enabled else "disabled",
        "kill_switch": "enabled" if config.execution.kill_switch_enabled else "disabled",
        "risk_limits": "configured" if config.risk.max_loss_per_trade >= 0 else "invalid",
        "persistence": "configured" if config.persistence.postgres_dsn and config.persistence.redis_url else "missing",
    }
    if config.execution.live_trading_enabled and not config.execution.kill_switch_enabled:
        checks["live_gate"] = "requires_operator_confirmation"
    status = "ready" if all(value not in {"missing", "invalid"} for value in checks.values()) else "not_ready"
    if config.execution.live_trading_enabled:
        status = "not_ready"
        checks["live_trading_guardrail"] = "manual_operator_checklist_required"
    return HealthResult(status=status, checks=checks)
