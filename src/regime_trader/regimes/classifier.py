from __future__ import annotations

from regime_trader.config.models import RegimeConfig
from regime_trader.schemas.regime import (
    DirectionalBias,
    FeatureVector,
    RegimeOutput,
    RegimeStatus,
    VolatilityRegime,
)


class RegimeClassifier:
    def __init__(self, config: RegimeConfig) -> None:
        self.config = config

    def classify(
        self,
        vector: FeatureVector,
        *,
        cluster_id: int | None = None,
        cluster_confidence: float | None = None,
    ) -> RegimeOutput:
        features = vector.as_dict()
        realized_vol = features.get("realized_volatility", 0.0)
        momentum = features.get("momentum", 0.0)
        wasserstein = features.get("wasserstein_distance", 0.0)
        entropy = features.get("entropy", 0.0)
        if realized_vol >= self.config.high_vol_threshold:
            volatility = VolatilityRegime.HIGH
        elif realized_vol <= self.config.low_vol_threshold:
            volatility = VolatilityRegime.LOW
        else:
            volatility = VolatilityRegime.MEDIUM
        if momentum > self.config.momentum_threshold:
            bias = DirectionalBias.BULLISH
        elif momentum < -self.config.momentum_threshold:
            bias = DirectionalBias.BEARISH
        else:
            bias = DirectionalBias.NEUTRAL
        confidence = self._confidence(realized_vol, momentum, wasserstein, entropy, cluster_confidence)
        status = RegimeStatus.CLASSIFIED if confidence >= self.config.confidence_threshold else RegimeStatus.UNCERTAIN
        drivers: list[str] = []
        if wasserstein >= self.config.wasserstein_spike_threshold:
            drivers.append("wasserstein_spike")
        if entropy >= self.config.entropy_uncertainty_threshold:
            drivers.append("high_entropy")
        if abs(momentum) >= self.config.momentum_threshold:
            drivers.append("momentum")
        drivers.append(f"{volatility}_volatility")
        label = f"{bias}_{volatility}_volatility"
        if status == RegimeStatus.UNCERTAIN:
            label = f"uncertain_{label}"
        return RegimeOutput(
            symbol=vector.symbol,
            timestamp=vector.timestamp,
            status=status,
            regime_label=label,
            volatility_regime=volatility,
            directional_bias=bias,
            confidence=confidence,
            cluster_id=cluster_id,
            key_drivers=tuple(drivers),
            feature_values=features,
            model_version=vector.model_version or self.config.model_version,
            classifier_version=self.config.classifier_version,
            feature_config_version=vector.feature_config_version,
            input_window_ref=vector.input_window_ref,
        )

    def _confidence(
        self,
        realized_vol: float,
        momentum: float,
        wasserstein: float,
        entropy: float,
        cluster_confidence: float | None,
    ) -> float:
        score = 0.50
        score += min(abs(momentum) / max(self.config.momentum_threshold * 4, 1e-9), 0.20)
        score += 0.10 if realized_vol > 0 else 0
        score -= min(wasserstein / max(self.config.wasserstein_spike_threshold * 4, 1e-9), 0.15)
        score -= 0.15 if entropy >= self.config.entropy_uncertainty_threshold else 0
        if cluster_confidence is not None:
            score = (score * 0.7) + (cluster_confidence * 0.3)
        return max(0.0, min(1.0, score))
