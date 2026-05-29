from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml
from pydantic import Field

from regime_trader.schemas.base import StrictModel
from regime_trader.schemas.market import AssetClass
from regime_trader.schemas.trading import ExecutionMode, StrategyType


class ProviderConfig(StrictModel):
    name: str = "public"
    api_secret_env: str = "PUBLIC_API_SECRET_KEY"
    account_id_env: str = "PUBLIC_DEFAULT_ACCOUNT_NUMBER"
    request_timeout_seconds: float = Field(default=10.0, gt=0)
    max_retries: int = Field(default=2, ge=0)
    backoff_seconds: float = Field(default=0.25, ge=0)
    cache_ttl_seconds: int = Field(default=30, ge=0)


class SymbolUniverseConfig(StrictModel):
    equities: tuple[str, ...] = ("SPY", "QQQ")
    option_underlyings: tuple[str, ...] = ("SPY",)
    crypto: tuple[str, ...] = ()

    def symbols_for(self, asset_class: AssetClass | None = None) -> tuple[str, ...]:
        if asset_class == AssetClass.CRYPTO:
            return self.crypto
        if asset_class == AssetClass.OPTION:
            return self.option_underlyings
        if asset_class in {AssetClass.EQUITY, AssetClass.ETF}:
            return self.equities
        return tuple(dict.fromkeys((*self.equities, *self.option_underlyings, *self.crypto)))


class FeatureConfig(StrictModel):
    lookback_bars: int = Field(default=30, ge=5)
    realized_vol_window: int = Field(default=10, ge=2)
    wasserstein_baseline_bars: int = Field(default=20, ge=5)
    entropy_bins: int = Field(default=8, ge=2)
    iv_rank_window: int = Field(default=52, ge=2)
    version: str = "features-v1"


class RegimeConfig(StrictModel):
    confidence_threshold: float = Field(default=0.55, ge=0, le=1)
    high_vol_threshold: float = Field(default=0.30, ge=0)
    low_vol_threshold: float = Field(default=0.12, ge=0)
    momentum_threshold: float = Field(default=0.01, ge=0)
    wasserstein_spike_threshold: float = Field(default=0.025, ge=0)
    entropy_uncertainty_threshold: float = Field(default=1.8, ge=0)
    cluster_count: int = Field(default=3, ge=2)
    model_version: str = "deterministic-kmeans-v1"
    classifier_version: str = "rule-classifier-v1"


class StrategyConfig(StrictModel):
    min_confidence: float = Field(default=0.60, ge=0, le=1)
    max_entropy_for_directional: float = Field(default=2.2, ge=0)
    max_bid_ask_spread: Decimal = Field(default=Decimal("0.40"), ge=0)
    min_open_interest: int = Field(default=1, ge=0)
    min_days_to_expiration: int = Field(default=14, ge=0)
    max_days_to_expiration: int = Field(default=60, ge=1)
    vertical_width: Decimal = Field(default=Decimal("5"), gt=0)
    max_contracts: int = Field(default=1, ge=1)
    mapping: dict[str, StrategyType] = Field(
        default_factory=lambda: {
            "bullish": StrategyType.BULL_CALL_SPREAD,
            "bearish": StrategyType.BEAR_PUT_SPREAD,
            "neutral": StrategyType.IRON_CONDOR,
        }
    )


class RiskConfig(StrictModel):
    max_loss_per_trade: Decimal = Field(default=Decimal("500"), ge=0)
    max_buying_power_fraction: Decimal = Field(default=Decimal("0.05"), ge=0, le=1)
    max_portfolio_delta_abs: float = Field(default=100.0, ge=0)
    max_symbol_concentration_fraction: Decimal = Field(default=Decimal("0.20"), ge=0, le=1)
    max_open_trades: int = Field(default=5, ge=0)
    min_regime_confidence: float = Field(default=0.55, ge=0, le=1)
    require_defined_max_loss: bool = True


class StreamingConfig(StrictModel):
    enabled: bool = False
    reconnect_attempts: int = Field(default=5, ge=0)
    reconnect_backoff_seconds: float = Field(default=1.0, ge=0)
    max_gap_seconds: int = Field(default=60, ge=1)
    update_interval_seconds: int = Field(default=30, ge=1)


class PersistenceConfig(StrictModel):
    redis_url: str = "redis://localhost:6379/0"
    postgres_dsn: str = "postgresql+psycopg://regime:regime@localhost:5432/regime"
    parquet_root: str = "data/parquet"
    live_state_ttl_seconds: int = Field(default=120, ge=1)


class ExecutionConfig(StrictModel):
    mode: ExecutionMode = ExecutionMode.DRY_RUN
    live_trading_enabled: bool = False
    require_operator_approval: bool = True
    kill_switch_enabled: bool = True


class AppConfig(StrictModel):
    provider: ProviderConfig = Field(default_factory=ProviderConfig)
    universe: SymbolUniverseConfig = Field(default_factory=SymbolUniverseConfig)
    features: FeatureConfig = Field(default_factory=FeatureConfig)
    regimes: RegimeConfig = Field(default_factory=RegimeConfig)
    strategies: StrategyConfig = Field(default_factory=StrategyConfig)
    risk: RiskConfig = Field(default_factory=RiskConfig)
    streaming: StreamingConfig = Field(default_factory=StreamingConfig)
    persistence: PersistenceConfig = Field(default_factory=PersistenceConfig)
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)

    @property
    def version(self) -> str:
        payload = self.model_dump(mode="json")
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def load_config(path: str | Path | None = None) -> AppConfig:
    if path is None:
        return AppConfig()
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError("configuration root must be a mapping")
    return AppConfig.model_validate(raw)


def config_version_for(raw: dict[str, Any]) -> str:
    canonical = json.dumps(raw, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]
