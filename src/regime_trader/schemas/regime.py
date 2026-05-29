from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import Field, field_validator

from regime_trader.schemas.base import StrictModel, ensure_utc


class VolatilityRegime(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class DirectionalBias(StrEnum):
    BEARISH = "bearish"
    NEUTRAL = "neutral"
    BULLISH = "bullish"


class RegimeStatus(StrEnum):
    CLASSIFIED = "classified"
    UNCERTAIN = "uncertain"
    INSUFFICIENT_DATA = "insufficient_data"


class FeatureValue(StrictModel):
    name: str
    value: float
    window_ref: str | None = None
    description: str | None = None


class FeatureVector(StrictModel):
    symbol: str
    timestamp: datetime
    features: tuple[FeatureValue, ...]
    input_window_ref: str
    feature_config_version: str
    model_version: str | None = None

    @field_validator("timestamp")
    @classmethod
    def _timestamp_utc(cls, value: datetime) -> datetime:
        return ensure_utc(value)

    def as_dict(self) -> dict[str, float]:
        return {feature.name: feature.value for feature in self.features}


class TransitionProbability(StrictModel):
    from_regime: str
    to_regime: str
    probability: float = Field(ge=0, le=1)
    observations: int = Field(ge=0)


class RegimeOutput(StrictModel):
    symbol: str
    timestamp: datetime
    status: RegimeStatus
    regime_label: str
    volatility_regime: VolatilityRegime
    directional_bias: DirectionalBias
    confidence: float = Field(ge=0, le=1)
    cluster_id: int | None = None
    key_drivers: tuple[str, ...] = ()
    feature_values: dict[str, float] = Field(default_factory=dict)
    transition_probabilities: tuple[TransitionProbability, ...] = ()
    model_version: str
    classifier_version: str
    feature_config_version: str
    input_window_ref: str

    @field_validator("timestamp")
    @classmethod
    def _timestamp_utc(cls, value: datetime) -> datetime:
        return ensure_utc(value)
