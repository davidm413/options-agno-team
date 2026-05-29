from __future__ import annotations

from regime_trader.config.models import AppConfig
from regime_trader.data.validation import validate_bar_history, validate_option_chain
from regime_trader.regimes.service import RegimeService
from regime_trader.service import DryRunWorkflow
from regime_trader.testing.fixtures import (
    FixtureProvider,
    fixture_account,
    fixture_bars,
    fixture_option_chain,
)
from regime_trader.trading.risk import RiskEngine
from regime_trader.trading.strategy import StrategyEngine


def test_data_quality_accepts_fixture_data() -> None:
    config = AppConfig()
    bars = fixture_bars(count=config.features.lookback_bars)
    chain = fixture_option_chain()
    assert validate_bar_history(bars, min_count=config.features.lookback_bars) == ()
    assert validate_option_chain(chain, max_age=chain.timestamp - chain.timestamp, now=chain.timestamp) == ()


def test_strategy_risk_and_dry_run_execution_path() -> None:
    config = AppConfig()
    regime = RegimeService(config.features, config.regimes).detect(
        "SPY", fixture_bars(), option_chain=fixture_option_chain()
    )
    proposal = StrategyEngine(config.strategies).propose(regime, fixture_option_chain(), config_version=config.version)
    decision = RiskEngine(config.risk).review(proposal, account=fixture_account())
    workflow = DryRunWorkflow(config=config, provider=FixtureProvider(config))
    execution = workflow.run_symbol("SPY", account=fixture_account())
    assert proposal.strategy_type != "no_trade"
    assert decision.approved
    assert execution.mode == "dry_run"
    assert execution.status == "approved"
