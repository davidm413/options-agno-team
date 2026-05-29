from __future__ import annotations

from regime_trader.scanner.anomaly import AnomalyFlag
from regime_trader.schemas.regime import RegimeOutput, RegimeStatus


def opportunity_score(output: RegimeOutput, anomalies: tuple[AnomalyFlag, ...], data_valid: bool) -> float:
    if output.status != RegimeStatus.CLASSIFIED or not data_valid:
        return 0.0
    directional = 0.15 if output.directional_bias != "neutral" else 0.05
    anomaly_penalty = min(0.25, len(anomalies) * 0.08)
    confidence = output.confidence
    liquidity = output.feature_values.get("liquidity_score", 0.5)
    spread = output.feature_values.get("spread_score", 0.5)
    return max(
        0.0,
        min(
            1.0,
            confidence * 0.55 + directional + liquidity * 0.15 + spread * 0.15 - anomaly_penalty,
        ),
    )
