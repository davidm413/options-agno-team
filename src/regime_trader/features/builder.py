from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from regime_trader.config.models import FeatureConfig
from regime_trader.features.calculations import (
    entropy,
    log_returns,
    momentum,
    rolling_realized_volatility,
    split_baseline_current,
    wasserstein_distance_1d,
)
from regime_trader.features.options import chain_average_iv, option_strength_metrics, skew
from regime_trader.schemas.market import Bar, OptionChain
from regime_trader.schemas.regime import FeatureValue, FeatureVector


def _close_prices(bars: Sequence[Bar]) -> list[float]:
    return [float(bar.close) for bar in bars]


class FeatureVectorBuilder:
    def __init__(self, config: FeatureConfig) -> None:
        self.config = config

    def build(
        self,
        symbol: str,
        bars: Sequence[Bar],
        *,
        option_chain: OptionChain | None = None,
        model_version: str | None = None,
    ) -> FeatureVector:
        if len(bars) < self.config.lookback_bars:
            raise ValueError(f"insufficient bars: expected {self.config.lookback_bars}, got {len(bars)}")
        selected = tuple(bars[-self.config.lookback_bars :])
        prices = _close_prices(selected)
        returns = log_returns(prices)
        returns_list = [float(value) for value in returns]
        baseline, current = split_baseline_current(
            returns_list, min(self.config.wasserstein_baseline_bars, len(returns_list) - 2)
        )
        baseline_list = [float(value) for value in baseline]
        current_list = [float(value) for value in current]
        values = [
            FeatureValue(
                name="log_return_last",
                value=float(returns[-1]),
                window_ref=f"{selected[-2].timestamp.isoformat()}:{selected[-1].timestamp.isoformat()}",
            ),
            FeatureValue(
                name="realized_volatility",
                value=rolling_realized_volatility(
                    returns_list,
                    min(self.config.realized_vol_window, len(returns_list)),
                ),
            ),
            FeatureValue(
                name="momentum",
                value=momentum(prices, min(10, len(prices) - 1)),
            ),
            FeatureValue(
                name="wasserstein_distance",
                value=wasserstein_distance_1d(current_list, baseline_list),
            ),
            FeatureValue(name="entropy", value=entropy(returns_list, self.config.entropy_bins)),
        ]
        if option_chain:
            avg_iv = chain_average_iv(option_chain)
            if avg_iv is not None:
                values.append(FeatureValue(name="implied_volatility", value=avg_iv))
            skew_value = skew(option_chain)
            if skew_value is not None:
                values.append(FeatureValue(name="iv_skew", value=skew_value))
            for name, value in option_strength_metrics(option_chain).items():
                values.append(FeatureValue(name=name, value=value))
        input_ref = (
            f"{symbol}:{selected[0].timestamp.isoformat()}:{selected[-1].timestamp.isoformat()}:"
            f"{Decimal(str(selected[-1].close))}"
        )
        return FeatureVector(
            symbol=symbol.upper(),
            timestamp=selected[-1].timestamp,
            features=tuple(values),
            input_window_ref=input_ref,
            feature_config_version=self.config.version,
            model_version=model_version,
        )
