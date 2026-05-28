from options_agno_team.adapters.fixture import FixtureMarketDataAdapter
from options_agno_team.features import FeatureEngine
from options_agno_team.models import DirectionalBias, VolatilityRegime
from options_agno_team.regime import RegimeEngine


def test_feature_engine_handles_flat_prices() -> None:
    adapter = FixtureMarketDataAdapter()
    features = FeatureEngine().build("FLAT", adapter.get_bars("FLAT", lookback=40))

    assert features.realized_volatility == 0
    assert features.entropy == 0
    assert features.wasserstein_distance == 0


def test_feature_engine_detects_high_volatility() -> None:
    adapter = FixtureMarketDataAdapter()
    features = FeatureEngine().build("HIGHVOL", adapter.get_bars("HIGHVOL", lookback=80))

    assert features.realized_volatility > 0.35
    assert features.entropy > 0


def test_regime_engine_classifies_bull_and_bear() -> None:
    adapter = FixtureMarketDataAdapter()
    feature_engine = FeatureEngine()
    regime_engine = RegimeEngine()

    bull = regime_engine.classify(
        feature_engine.build("BULL", adapter.get_bars("BULL", lookback=80))
    )
    bear = regime_engine.classify(
        feature_engine.build("BEAR", adapter.get_bars("BEAR", lookback=80))
    )

    assert bull.directional_bias is DirectionalBias.BULLISH
    assert bear.directional_bias is DirectionalBias.BEARISH
    assert bull.volatility_regime in {
        VolatilityRegime.LOW,
        VolatilityRegime.MEDIUM,
        VolatilityRegime.HIGH,
    }
    assert bull.confidence > 0
