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
    public_api_secret_key: str | None = None
    public_default_account_number: str | None = None
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
            public_api_secret_key=values.get("API_SECRET_KEY"),
            public_default_account_number=values.get("DEFAULT_ACCOUNT_NUMBER"),
        )

    @property
    def live_order_enabled(self) -> bool:
        return self.execution_mode is ExecutionMode.LIVE and self.enable_live_trading


def _parse_bool(value: str | None, *, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}
