"""Deterministic feature engineering."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from statistics import mean, pstdev

from options_agno_team.models import FeatureSnapshot, NormalizedBar, OptionContractQuote, OptionType


class FeatureEngine:
    def build(
        self,
        symbol: str,
        bars: list[NormalizedBar],
        *,
        option_chain: list[OptionContractQuote] | None = None,
    ) -> FeatureSnapshot:
        if len(bars) < 3:
            raise ValueError("At least 3 bars are required to build features")
        sorted_bars = sorted(bars, key=lambda bar: bar.timestamp)
        closes = [bar.close for bar in sorted_bars]
        returns = _log_returns(closes)
        realized_vol = _annualized_volatility(returns[-30:])
        current = returns[-20:] if len(returns) >= 20 else returns
        history = returns[:-20] if len(returns) > 25 else returns[: max(1, len(returns) // 2)]
        wasserstein = _wasserstein_1d(history, current)
        entropy = _entropy(current)
        momentum_window = min(20, len(closes) - 1)
        momentum = closes[-1] / closes[-1 - momentum_window] - 1 if momentum_window else 0.0
        iv_rank, skew, term_slope = _options_features(option_chain or [])
        vector = (
            realized_vol,
            wasserstein,
            entropy,
            momentum,
            iv_rank or 0.0,
            skew or 0.0,
            term_slope or 0.0,
        )
        return FeatureSnapshot(
            symbol=symbol.upper(),
            timestamp=sorted_bars[-1].timestamp or datetime.now(timezone.utc),
            returns=tuple(returns),
            realized_volatility=realized_vol,
            wasserstein_distance=wasserstein,
            entropy=entropy,
            momentum=momentum,
            iv_rank=iv_rank,
            skew=skew,
            term_structure_slope=term_slope,
            feature_vector=vector,
        )


def _log_returns(closes: list[float]) -> list[float]:
    returns: list[float] = []
    for previous, current in zip(closes, closes[1:]):
        if previous <= 0 or current <= 0:
            returns.append(0.0)
        else:
            returns.append(math.log(current / previous))
    return returns


def _annualized_volatility(returns: list[float]) -> float:
    if len(returns) < 2:
        return 0.0
    return pstdev(returns) * math.sqrt(252)


def _wasserstein_1d(reference: list[float], current: list[float]) -> float:
    if not reference or not current:
        return 0.0
    count = max(len(reference), len(current))
    ref_q = _quantiles(sorted(reference), count)
    cur_q = _quantiles(sorted(current), count)
    return sum(abs(a - b) for a, b in zip(ref_q, cur_q)) / count


def _quantiles(values: list[float], count: int) -> list[float]:
    if len(values) == count:
        return values
    if len(values) == 1:
        return values * count
    result: list[float] = []
    for index in range(count):
        position = index * (len(values) - 1) / max(count - 1, 1)
        lower = math.floor(position)
        upper = math.ceil(position)
        weight = position - lower
        result.append(values[lower] * (1 - weight) + values[upper] * weight)
    return result


def _entropy(values: list[float], *, bins: int = 8) -> float:
    if len(values) < 2:
        return 0.0
    low = min(values)
    high = max(values)
    if math.isclose(low, high):
        return 0.0
    width = (high - low) / bins
    counts = [0] * bins
    for value in values:
        bucket = min(bins - 1, int((value - low) / width))
        counts[bucket] += 1
    total = sum(counts)
    probabilities = [count / total for count in counts if count]
    return -sum(prob * math.log(prob) for prob in probabilities)


def _options_features(
    option_chain: list[OptionContractQuote],
) -> tuple[float | None, float | None, float | None]:
    ivs = [option.implied_volatility for option in option_chain if option.implied_volatility is not None]
    if not ivs:
        return None, None, None
    iv_min = min(ivs)
    iv_max = max(ivs)
    median_iv = sorted(ivs)[len(ivs) // 2]
    iv_rank = 0.0 if math.isclose(iv_max, iv_min) else (median_iv - iv_min) / (iv_max - iv_min) * 100

    call_ivs = [
        option.implied_volatility
        for option in option_chain
        if option.option_type is OptionType.CALL and option.implied_volatility is not None
    ]
    put_ivs = [
        option.implied_volatility
        for option in option_chain
        if option.option_type is OptionType.PUT and option.implied_volatility is not None
    ]
    skew = mean(put_ivs) - mean(call_ivs) if call_ivs and put_ivs else None

    expirations = sorted({option.expiration_date for option in option_chain})
    term_slope = None
    if len(expirations) >= 2:
        near = [
            option.implied_volatility
            for option in option_chain
            if option.expiration_date == expirations[0] and option.implied_volatility is not None
        ]
        far = [
            option.implied_volatility
            for option in option_chain
            if option.expiration_date == expirations[-1] and option.implied_volatility is not None
        ]
        if near and far:
            term_slope = mean(far) - mean(near)
    return round(iv_rank, 4), round(skew, 4) if skew is not None else None, round(term_slope, 4) if term_slope is not None else None
