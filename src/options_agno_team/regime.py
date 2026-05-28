"""Deterministic regime classification."""

from __future__ import annotations

from options_agno_team.models import (
    DirectionalBias,
    FeatureSnapshot,
    RegimeSnapshot,
    VolatilityRegime,
)


class RegimeEngine:
    def classify(self, features: FeatureSnapshot) -> RegimeSnapshot:
        volatility = _volatility_regime(features.realized_volatility)
        bias = _directional_bias(features.momentum)
        label = _label(volatility, bias, features.wasserstein_distance)
        confidence = _confidence(features, bias)
        cluster_id = _cluster_id(volatility, bias, features.wasserstein_distance)
        drivers = _drivers(features, volatility, bias)
        transitions = _transition_probability(features, volatility)
        return RegimeSnapshot(
            symbol=features.symbol,
            timestamp=features.timestamp,
            volatility_regime=volatility,
            directional_bias=bias,
            regime_label=label,
            cluster_id=cluster_id,
            confidence=confidence,
            wasserstein_distance=features.wasserstein_distance,
            entropy=features.entropy,
            key_drivers=drivers,
            transition_probability=transitions,
            features=features,
        )


def _volatility_regime(realized_volatility: float) -> VolatilityRegime:
    if realized_volatility < 0.15:
        return VolatilityRegime.LOW
    if realized_volatility > 0.35:
        return VolatilityRegime.HIGH
    return VolatilityRegime.MEDIUM


def _directional_bias(momentum: float) -> DirectionalBias:
    if momentum > 0.03:
        return DirectionalBias.BULLISH
    if momentum < -0.03:
        return DirectionalBias.BEARISH
    return DirectionalBias.NEUTRAL_CHOPPY


def _label(
    volatility: VolatilityRegime, bias: DirectionalBias, wasserstein_distance: float
) -> str:
    if wasserstein_distance > 0.035:
        stability = "unstable"
    elif volatility is VolatilityRegime.HIGH:
        stability = "stress"
    elif volatility is VolatilityRegime.LOW:
        stability = "compression"
    else:
        stability = "expansion"

    if bias is DirectionalBias.BULLISH:
        direction = "risk_on"
    elif bias is DirectionalBias.BEARISH:
        direction = "risk_off"
    else:
        direction = "neutral"
    return f"{direction}_{stability}"


def _confidence(features: FeatureSnapshot, bias: DirectionalBias) -> float:
    score = 0.55
    score += min(abs(features.momentum) / 0.12, 0.2)
    score += 0.12 if features.wasserstein_distance < 0.02 else -0.08
    score += 0.06 if features.entropy < 2.0 else -0.06
    if bias is DirectionalBias.NEUTRAL_CHOPPY:
        score -= 0.04
    return round(max(0.05, min(0.95, score)), 4)


def _cluster_id(
    volatility: VolatilityRegime, bias: DirectionalBias, wasserstein_distance: float
) -> int:
    volatility_index = {
        VolatilityRegime.LOW: 0,
        VolatilityRegime.MEDIUM: 1,
        VolatilityRegime.HIGH: 2,
    }[volatility]
    bias_index = {
        DirectionalBias.BULLISH: 0,
        DirectionalBias.NEUTRAL_CHOPPY: 1,
        DirectionalBias.BEARISH: 2,
    }[bias]
    unstable = 1 if wasserstein_distance > 0.035 else 0
    return volatility_index * 3 + bias_index + unstable


def _drivers(
    features: FeatureSnapshot, volatility: VolatilityRegime, bias: DirectionalBias
) -> tuple[str, ...]:
    drivers = [
        f"volatility_{volatility.value}",
        f"bias_{bias.value}",
        f"momentum_{features.momentum:.4f}",
        f"wasserstein_{features.wasserstein_distance:.4f}",
        f"entropy_{features.entropy:.4f}",
    ]
    if features.iv_rank is not None:
        drivers.append(f"iv_rank_{features.iv_rank:.1f}")
    if features.skew is not None:
        drivers.append(f"skew_{features.skew:.4f}")
    return tuple(drivers)


def _transition_probability(
    features: FeatureSnapshot, volatility: VolatilityRegime
) -> dict[str, float]:
    instability = min(features.wasserstein_distance / 0.08, 1.0)
    high_entropy = min(features.entropy / 3.0, 1.0)
    to_risk_off = 0.08 + instability * 0.25 + high_entropy * 0.12
    to_high_vol = 0.06 + instability * 0.3
    if volatility is VolatilityRegime.HIGH:
        to_high_vol = max(to_high_vol, 0.65)
    return {
        "to_risk_off": round(min(to_risk_off, 0.9), 4),
        "to_high_volatility": round(min(to_high_vol, 0.9), 4),
    }
