from __future__ import annotations

from regime_trader.config.models import AppConfig
from regime_trader.features.calculations import entropy, log_returns, wasserstein_distance_1d
from regime_trader.regimes.service import RegimeService
from regime_trader.schemas.regime import RegimeStatus
from regime_trader.testing.fixtures import fixture_bars, fixture_option_chain


def test_feature_math_is_deterministic() -> None:
    returns = log_returns([100, 101, 103, 102])
    assert returns.tolist() == log_returns([100, 101, 103, 102]).tolist()
    assert wasserstein_distance_1d([0.01, 0.02], [0.00, 0.01]) > 0
    assert entropy(returns, 3) >= 0


def test_regime_service_returns_reproducible_metadata() -> None:
    config = AppConfig()
    service = RegimeService(config.features, config.regimes)
    output = service.detect("SPY", fixture_bars(), option_chain=fixture_option_chain())
    assert output.status in {RegimeStatus.CLASSIFIED, RegimeStatus.UNCERTAIN}
    assert output.feature_config_version == config.features.version
    assert output.model_version == config.regimes.model_version
    assert "wasserstein_distance" in output.feature_values
