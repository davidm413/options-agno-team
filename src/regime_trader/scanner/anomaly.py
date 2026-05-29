from __future__ import annotations

from pydantic import Field

from regime_trader.config.models import RegimeConfig
from regime_trader.schemas.base import StrictModel, utc_now
from regime_trader.schemas.regime import RegimeOutput


class AnomalyFlag(StrictModel):
    anomaly_type: str
    severity: str
    symbol: str
    value: float
    threshold: float
    timestamp: str = Field(default_factory=lambda: utc_now().isoformat())


def detect_anomalies(output: RegimeOutput, config: RegimeConfig) -> tuple[AnomalyFlag, ...]:
    flags: list[AnomalyFlag] = []
    wasserstein = output.feature_values.get("wasserstein_distance", 0.0)
    entropy = output.feature_values.get("entropy", 0.0)
    volatility = output.feature_values.get("realized_volatility", 0.0)
    if wasserstein >= config.wasserstein_spike_threshold:
        flags.append(
            AnomalyFlag(
                anomaly_type="wasserstein_spike",
                severity="high",
                symbol=output.symbol,
                value=wasserstein,
                threshold=config.wasserstein_spike_threshold,
            )
        )
    if entropy >= config.entropy_uncertainty_threshold:
        flags.append(
            AnomalyFlag(
                anomaly_type="entropy_jump",
                severity="medium",
                symbol=output.symbol,
                value=entropy,
                threshold=config.entropy_uncertainty_threshold,
            )
        )
    if volatility >= config.high_vol_threshold:
        flags.append(
            AnomalyFlag(
                anomaly_type="volatility_shift",
                severity="medium",
                symbol=output.symbol,
                value=volatility,
                threshold=config.high_vol_threshold,
            )
        )
    return tuple(flags)
