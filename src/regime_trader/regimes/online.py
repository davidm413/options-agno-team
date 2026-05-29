from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Sequence

from regime_trader.config.models import FeatureConfig, RegimeConfig, StreamingConfig
from regime_trader.regimes.service import RegimeService
from regime_trader.schemas.market import Bar
from regime_trader.schemas.regime import RegimeOutput


class OnlineRegimeUpdater:
    def __init__(
        self,
        feature_config: FeatureConfig,
        regime_config: RegimeConfig,
        streaming_config: StreamingConfig,
    ) -> None:
        self.service = RegimeService(feature_config, regime_config)
        self.streaming_config = streaming_config
        self.windows: dict[str, deque[Bar]] = defaultdict(lambda: deque(maxlen=feature_config.lookback_bars))
        self.latest: dict[str, RegimeOutput] = {}

    def update(self, bar: Bar) -> RegimeOutput | None:
        window = self.windows[bar.symbol]
        window.append(bar)
        required = window.maxlen or 0
        if len(window) < required:
            return None
        previous = self.latest.get(bar.symbol)
        output = self.service.detect(bar.symbol, tuple(window), history=(previous,) if previous else ())
        if previous is None or output.regime_label != previous.regime_label:
            self.latest[bar.symbol] = output
            return output
        self.latest[bar.symbol] = output
        return None

    def seed(self, symbol: str, bars: Sequence[Bar]) -> None:
        for bar in bars:
            self.windows[symbol].append(bar)
