"""Runtime configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping


class DataMode(str, Enum):
    FIXTURE = "fixture"
    PUBLIC = "public"


class ExecutionMode(str, Enum):
    DRY_RUN = "dry_run"
    LIVE = "live"


@dataclass(frozen=True)
class AppConfig:
    data_mode: DataMode = DataMode.FIXTURE
    execution_mode: ExecutionMode = ExecutionMode.DRY_RUN
    enable_live_trading: bool = False
    default_symbols: tuple[str, ...] = ("SPY", "QQQ", "TSLA", "NVDA")
    max_risk_per_trade: float = 0.02
    max_portfolio_delta: float = 0.15
    min_regime_confidence: float = 0.55
    max_entropy_for_entry: float = 2.6
    default_quantity: int = 1
    option_min_dte: int = 21
    option_max_dte: int = 60
    option_target_long_delta: float = 0.55
    option_target_short_delta: float = 0.30
    option_target_hedge_delta: float = 0.15
    option_min_open_interest: int = 100
    option_min_volume: int = 10
    option_max_bid_ask_width: float = 0.50
    option_max_bid_ask_pct: float = 0.50
    option_min_spread_width: float = 1.0
    option_min_spread_width_pct: float = 0.005
    option_preferred_spread_width_pct: float = 0.04
    option_max_spread_width_pct: float = 0.12
    option_min_iv_rank: float = 0.0
    option_max_iv_rank: float = 100.0
    profit_target_pct: float = 0.50
    stop_loss_pct: float = 0.50
    time_decay_exit_dte: int = 7
    max_days_in_trade: int = 30
    max_position_delta_abs: float = 0.35
    entropy_spike_delta: float = 0.35
    kill_switch_enabled: bool = False
    daily_loss_limit: float = 1_000.0
    max_open_trades: int = 5
    max_trades_per_day: int = 10
    live_confirmation_required: str = "CONFIRM LIVE OPTIONS TRADING"
    live_confirmation: str | None = None
    live_risk_limits_confirmed: bool = False
    live_alerting_confirmed: bool = False
    alert_stdout_enabled: bool = False
    alert_webhook_url: str | None = None
    alert_webhook_timeout_seconds: float = 2.0
    public_api_secret_key: str | None = None
    public_default_account_number: str | None = None
    audit_db_path: str | None = None
    allowed_live_strategies: tuple[str, ...] = field(
        default=(
            "bull_call_debit_spread",
            "bear_put_debit_spread",
            "bull_put_credit_spread",
            "bear_call_credit_spread",
        )
    )

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "AppConfig":
        values = env if env is not None else os.environ
        symbols = values.get("SYMBOLS")
        return cls(
            data_mode=DataMode(values.get("DATA_MODE", DataMode.FIXTURE.value).lower()),
            execution_mode=ExecutionMode(
                values.get("EXECUTION_MODE", ExecutionMode.DRY_RUN.value).lower()
            ),
            enable_live_trading=_parse_bool(values.get("ENABLE_LIVE_TRADING"), default=False),
            default_symbols=tuple(s.strip().upper() for s in symbols.split(","))
            if symbols
            else cls.default_symbols,
            max_risk_per_trade=float(values.get("MAX_RISK_PER_TRADE", cls.max_risk_per_trade)),
            max_portfolio_delta=float(values.get("MAX_PORTFOLIO_DELTA", cls.max_portfolio_delta)),
            min_regime_confidence=float(
                values.get("MIN_REGIME_CONFIDENCE", cls.min_regime_confidence)
            ),
            max_entropy_for_entry=float(
                values.get("MAX_ENTROPY_FOR_ENTRY", cls.max_entropy_for_entry)
            ),
            default_quantity=int(values.get("DEFAULT_QUANTITY", cls.default_quantity)),
            option_min_dte=int(values.get("OPTION_MIN_DTE", cls.option_min_dte)),
            option_max_dte=int(values.get("OPTION_MAX_DTE", cls.option_max_dte)),
            option_target_long_delta=float(
                values.get("OPTION_TARGET_LONG_DELTA", cls.option_target_long_delta)
            ),
            option_target_short_delta=float(
                values.get("OPTION_TARGET_SHORT_DELTA", cls.option_target_short_delta)
            ),
            option_target_hedge_delta=float(
                values.get("OPTION_TARGET_HEDGE_DELTA", cls.option_target_hedge_delta)
            ),
            option_min_open_interest=int(
                values.get("OPTION_MIN_OPEN_INTEREST", cls.option_min_open_interest)
            ),
            option_min_volume=int(values.get("OPTION_MIN_VOLUME", cls.option_min_volume)),
            option_max_bid_ask_width=float(
                values.get("OPTION_MAX_BID_ASK_WIDTH", cls.option_max_bid_ask_width)
            ),
            option_max_bid_ask_pct=float(
                values.get("OPTION_MAX_BID_ASK_PCT", cls.option_max_bid_ask_pct)
            ),
            option_min_spread_width=float(
                values.get("OPTION_MIN_SPREAD_WIDTH", cls.option_min_spread_width)
            ),
            option_min_spread_width_pct=float(
                values.get("OPTION_MIN_SPREAD_WIDTH_PCT", cls.option_min_spread_width_pct)
            ),
            option_preferred_spread_width_pct=float(
                values.get(
                    "OPTION_PREFERRED_SPREAD_WIDTH_PCT",
                    cls.option_preferred_spread_width_pct,
                )
            ),
            option_max_spread_width_pct=float(
                values.get("OPTION_MAX_SPREAD_WIDTH_PCT", cls.option_max_spread_width_pct)
            ),
            option_min_iv_rank=float(values.get("OPTION_MIN_IV_RANK", cls.option_min_iv_rank)),
            option_max_iv_rank=float(values.get("OPTION_MAX_IV_RANK", cls.option_max_iv_rank)),
            profit_target_pct=float(values.get("PROFIT_TARGET_PCT", cls.profit_target_pct)),
            stop_loss_pct=float(values.get("STOP_LOSS_PCT", cls.stop_loss_pct)),
            time_decay_exit_dte=int(values.get("TIME_DECAY_EXIT_DTE", cls.time_decay_exit_dte)),
            max_days_in_trade=int(values.get("MAX_DAYS_IN_TRADE", cls.max_days_in_trade)),
            max_position_delta_abs=float(
                values.get("MAX_POSITION_DELTA_ABS", cls.max_position_delta_abs)
            ),
            entropy_spike_delta=float(values.get("ENTROPY_SPIKE_DELTA", cls.entropy_spike_delta)),
            kill_switch_enabled=_parse_bool(
                values.get("KILL_SWITCH_ENABLED"), default=cls.kill_switch_enabled
            ),
            daily_loss_limit=float(values.get("DAILY_LOSS_LIMIT", cls.daily_loss_limit)),
            max_open_trades=int(values.get("MAX_OPEN_TRADES", cls.max_open_trades)),
            max_trades_per_day=int(values.get("MAX_TRADES_PER_DAY", cls.max_trades_per_day)),
            live_confirmation_required=values.get(
                "LIVE_CONFIRMATION_REQUIRED", cls.live_confirmation_required
            ),
            live_confirmation=values.get("LIVE_CONFIRMATION"),
            live_risk_limits_confirmed=_parse_bool(
                values.get("LIVE_RISK_LIMITS_CONFIRMED"),
                default=cls.live_risk_limits_confirmed,
            ),
            live_alerting_confirmed=_parse_bool(
                values.get("LIVE_ALERTING_CONFIRMED"),
                default=cls.live_alerting_confirmed,
            ),
            alert_stdout_enabled=_parse_bool(
                values.get("ALERT_STDOUT_ENABLED"),
                default=cls.alert_stdout_enabled,
            ),
            alert_webhook_url=values.get("ALERT_WEBHOOK_URL"),
            alert_webhook_timeout_seconds=float(
                values.get(
                    "ALERT_WEBHOOK_TIMEOUT_SECONDS",
                    cls.alert_webhook_timeout_seconds,
                )
            ),
            public_api_secret_key=values.get("API_SECRET_KEY"),
            public_default_account_number=values.get("DEFAULT_ACCOUNT_NUMBER"),
            audit_db_path=values.get("AUDIT_DB_PATH"),
        )

    @property
    def live_confirmation_matches(self) -> bool:
        return self.live_confirmation == self.live_confirmation_required

    @property
    def alerting_enabled(self) -> bool:
        return self.alert_stdout_enabled or bool(self.alert_webhook_url)

    @property
    def live_order_enabled(self) -> bool:
        return (
            self.execution_mode is ExecutionMode.LIVE
            and self.enable_live_trading
            and self.live_confirmation_matches
            and self.live_risk_limits_confirmed
            and self.live_alerting_confirmed
            and self.alerting_enabled
            and not self.kill_switch_enabled
            and self.daily_loss_limit > 0
            and self.max_open_trades > 0
            and self.max_trades_per_day > 0
        )


def _parse_bool(value: str | None, *, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}
