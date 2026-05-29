"""Live trading readiness checks."""

from __future__ import annotations

from options_agno_team.config import AppConfig, ExecutionMode
from options_agno_team.models import LiveReadinessReport


def evaluate_live_readiness(config: AppConfig) -> LiveReadinessReport:
    checks: dict[str, bool] = {}
    blockers: list[str] = []

    def require(name: str, passed: bool, blocker: str) -> None:
        checks[name] = passed
        if not passed:
            blockers.append(blocker)

    require("execution_mode_live", config.execution_mode is ExecutionMode.LIVE, "Set EXECUTION_MODE=live")
    require("enable_live_trading", config.enable_live_trading, "Set ENABLE_LIVE_TRADING=true")
    require(
        "live_confirmation_phrase",
        config.live_confirmation_matches,
        f'Set LIVE_CONFIRMATION="{config.live_confirmation_required}"',
    )
    require(
        "risk_limits_confirmed",
        config.live_risk_limits_confirmed,
        "Set LIVE_RISK_LIMITS_CONFIRMED=true after reviewing live risk limits",
    )
    require(
        "alerting_confirmed",
        config.live_alerting_confirmed,
        "Set LIVE_ALERTING_CONFIRMED=true after validating alert delivery",
    )
    require(
        "alerting_enabled",
        config.alerting_enabled,
        "Configure ALERT_WEBHOOK_URL or ALERT_STDOUT_ENABLED=true",
    )
    require("kill_switch_disabled", not config.kill_switch_enabled, "Disable KILL_SWITCH_ENABLED")
    require(
        "daily_loss_limit_positive",
        config.daily_loss_limit > 0,
        "Set DAILY_LOSS_LIMIT to a positive value",
    )
    require(
        "max_open_trades_positive",
        config.max_open_trades > 0,
        "Set MAX_OPEN_TRADES to a positive integer",
    )
    require(
        "max_trades_per_day_positive",
        config.max_trades_per_day > 0,
        "Set MAX_TRADES_PER_DAY to a positive integer",
    )

    return LiveReadinessReport(
        ready=not blockers,
        execution_mode=config.execution_mode.value,
        checks=checks,
        blockers=tuple(blockers),
        confirmations=tuple(
            item
            for item, confirmed in (
                ("live_confirmation_phrase", config.live_confirmation_matches),
                ("risk_limits_reviewed", config.live_risk_limits_confirmed),
                ("alerting_delivery_validated", config.live_alerting_confirmed),
            )
            if confirmed
        ),
        risk_limits={
            "kill_switch_enabled": config.kill_switch_enabled,
            "daily_loss_limit": config.daily_loss_limit,
            "max_open_trades": config.max_open_trades,
            "max_trades_per_day": config.max_trades_per_day,
            "max_risk_per_trade": config.max_risk_per_trade,
        },
        alerting={
            "enabled": config.alerting_enabled,
            "stdout_enabled": config.alert_stdout_enabled,
            "webhook_configured": bool(config.alert_webhook_url),
            "confirmed": config.live_alerting_confirmed,
        },
    )
