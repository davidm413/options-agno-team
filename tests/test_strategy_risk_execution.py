from types import SimpleNamespace
from unittest.mock import MagicMock

from options_agno_team.adapters.fixture import FixtureMarketDataAdapter
from options_agno_team.config import AppConfig, ExecutionMode
from options_agno_team.execution import ExecutionGateway
from options_agno_team.features import FeatureEngine
from options_agno_team.models import ExecutionStatus, RiskStatus, StrategyType
from options_agno_team.regime import RegimeEngine
from options_agno_team.risk import RiskEngine
from options_agno_team.strategy import StrategyEngine


def _proposal(symbol: str = "BULL"):
    adapter = FixtureMarketDataAdapter()
    features = FeatureEngine().build(symbol, adapter.get_bars(symbol, lookback=80))
    regime = RegimeEngine().classify(features)
    proposal = StrategyEngine(adapter).propose(regime)
    return adapter, proposal


def test_strategy_engine_maps_supported_spread() -> None:
    _, proposal = _proposal("BULL")

    assert proposal.strategy_type in {
        StrategyType.BULL_CALL_DEBIT_SPREAD,
        StrategyType.BULL_PUT_CREDIT_SPREAD,
    }
    assert proposal.legs
    assert proposal.max_loss > 0


def test_risk_engine_rejects_oversized_trade() -> None:
    adapter, proposal = _proposal("BULL")
    config = AppConfig(max_risk_per_trade=0.000001)

    decision = RiskEngine(adapter, config).evaluate(proposal)

    assert decision.status is RiskStatus.REJECTED
    assert any("exceeds risk_budget" in reason for reason in decision.reasons)


def test_dry_run_execution_never_calls_public_client() -> None:
    _, proposal = _proposal("BULL")
    risk = MagicMock(approved=True)
    public_client = MagicMock()
    gateway = ExecutionGateway(config=AppConfig(), public_client=public_client)

    result = gateway.execute(proposal, risk)

    assert result.status is ExecutionStatus.DRY_RUN
    public_client.assert_not_called()


def test_live_execution_requires_flags_and_preflight() -> None:
    _, proposal = _proposal("BULL")
    risk = MagicMock(approved=True)
    public_client = MagicMock()
    public_client.preflight_call_debit_spread.return_value = {"ok": True}
    public_client.place_call_debit_spread.return_value = SimpleNamespace(order_id="ORDER-1")
    config = AppConfig(execution_mode=ExecutionMode.LIVE, enable_live_trading=True)
    gateway = ExecutionGateway(config=config, public_client=public_client)

    if proposal.strategy_type is not StrategyType.BULL_CALL_DEBIT_SPREAD:
        proposal = proposal.__class__(
            **{**proposal.__dict__, "strategy_type": StrategyType.BULL_CALL_DEBIT_SPREAD}
        )

    result = gateway.execute(proposal, risk)

    assert result.status is ExecutionStatus.PLACED
    assert result.order_id == "ORDER-1"
    public_client.preflight_call_debit_spread.assert_called_once()
    public_client.place_call_debit_spread.assert_called_once()


def test_live_execution_rejected_when_flag_disabled() -> None:
    _, proposal = _proposal("BULL")
    risk = MagicMock(approved=True)
    public_client = MagicMock()
    gateway = ExecutionGateway(
        config=AppConfig(execution_mode=ExecutionMode.LIVE, enable_live_trading=False),
        public_client=public_client,
    )

    result = gateway.execute(proposal, risk)

    assert result.status is ExecutionStatus.REJECTED
    assert "disabled" in result.message
    assert public_client.method_calls == []
