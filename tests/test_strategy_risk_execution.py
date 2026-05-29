from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from options_agno_team.adapters.fixture import FixtureMarketDataAdapter
from options_agno_team.config import AppConfig, ExecutionMode
from options_agno_team.execution import ExecutionGateway
from options_agno_team.features import FeatureEngine
from options_agno_team.models import ExecutionStatus, OptionContractQuote, OptionType, RiskStatus, StrategyType
from options_agno_team.option_selection import OptionSelector
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


def test_risk_engine_enforces_live_safety_limits() -> None:
    adapter, proposal = _proposal("BULL")
    adapter._account["day_pnl"] = -250.0
    adapter._account["trades_today"] = 2
    config = AppConfig(daily_loss_limit=100.0, max_open_trades=1, max_trades_per_day=2)

    decision = RiskEngine(adapter, config).evaluate(proposal)

    assert decision.status is RiskStatus.REJECTED
    assert any("daily_loss_limit" in reason for reason in decision.reasons)
    assert any("max_open_trades" in reason for reason in decision.reasons)
    assert any("max_trades_per_day" in reason for reason in decision.reasons)


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
    config = AppConfig(
        execution_mode=ExecutionMode.LIVE,
        enable_live_trading=True,
        live_confirmation=AppConfig.live_confirmation_required,
        live_risk_limits_confirmed=True,
        live_alerting_confirmed=True,
        alert_stdout_enabled=True,
    )
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
        config=AppConfig(
            execution_mode=ExecutionMode.LIVE,
            enable_live_trading=False,
            live_confirmation=AppConfig.live_confirmation_required,
            live_risk_limits_confirmed=True,
            live_alerting_confirmed=True,
            alert_stdout_enabled=True,
        ),
        public_client=public_client,
    )

    result = gateway.execute(proposal, risk)

    assert result.status is ExecutionStatus.REJECTED
    assert "ENABLE_LIVE_TRADING" in result.message
    assert public_client.method_calls == []


def test_live_execution_rejected_until_alerting_is_confirmed() -> None:
    _, proposal = _proposal("BULL")
    risk = MagicMock(approved=True)
    public_client = MagicMock()
    gateway = ExecutionGateway(
        config=AppConfig(
            execution_mode=ExecutionMode.LIVE,
            enable_live_trading=True,
            live_confirmation=AppConfig.live_confirmation_required,
            live_risk_limits_confirmed=True,
        ),
        public_client=public_client,
    )

    result = gateway.execute(proposal, risk)

    assert result.status is ExecutionStatus.REJECTED
    assert "LIVE_ALERTING_CONFIRMED" in result.message
    assert "ALERT_WEBHOOK_URL" in result.message
    assert public_client.method_calls == []


class _SelectionAdapter:
    def __init__(self, chain_by_expiration: dict[str, list[OptionContractQuote]]) -> None:
        self.chain_by_expiration = chain_by_expiration

    def get_option_expirations(self, symbol: str) -> list[str]:
        return list(self.chain_by_expiration)

    def get_option_chain(
        self,
        symbol: str,
        *,
        expiration_date: str | None = None,
    ) -> list[OptionContractQuote]:
        if expiration_date is None:
            return [option for chain in self.chain_by_expiration.values() for option in chain]
        return self.chain_by_expiration[expiration_date]


def test_option_selector_prioritizes_delta_width_liquidity_and_open_interest() -> None:
    expiration = "2026-06-26"
    adapter = _SelectionAdapter(
        {
            expiration: [
                _call(expiration, 100, 0.48, 5.20, open_interest=50, volume=4, spread=0.70),
                _call(expiration, 105, 0.32, 2.20, open_interest=40, volume=3, spread=0.70),
                _call(expiration, 95, 0.55, 7.80, open_interest=6_000, volume=900, spread=0.10),
                _call(expiration, 105, 0.30, 2.80, open_interest=7_000, volume=950, spread=0.10),
                _call(expiration, 90, 0.72, 11.40, open_interest=8_000, volume=1_100, spread=0.10),
                _call(expiration, 110, 0.15, 1.10, open_interest=8_000, volume=1_100, spread=0.10),
            ]
        }
    )
    config = AppConfig(
        option_min_open_interest=100,
        option_min_volume=10,
        option_max_bid_ask_width=0.25,
        option_max_bid_ask_pct=0.25,
        option_min_spread_width=5.0,
        option_preferred_spread_width_pct=0.10,
        option_max_spread_width_pct=0.20,
    )

    selection = OptionSelector(adapter, config).select(
        StrategyType.BULL_CALL_DEBIT_SPREAD,
        "BULL",
        spot=100.0,
        quantity=1,
        as_of=FixtureMarketDataAdapter().now,
        iv_rank=42.0,
    )

    assert [leg.strike for leg in selection.legs] == [95, 105]
    assert any("min_open_interest=6000" in item for item in selection.rationale)
    assert any("bid_ask_pct=" in item for item in selection.rationale)


def test_option_selector_enforces_expiration_window_and_iv_rank() -> None:
    adapter = _SelectionAdapter(
        {
            "2026-06-05": [
                _call("2026-06-05", 95, 0.55, 7.80),
                _call("2026-06-05", 105, 0.30, 2.80),
            ],
            "2026-06-26": [
                _call("2026-06-26", 95, 0.55, 7.80),
                _call("2026-06-26", 105, 0.30, 2.80),
            ],
        }
    )
    selector = OptionSelector(adapter, AppConfig(option_min_iv_rank=20.0))

    selection = selector.select(
        StrategyType.BULL_CALL_DEBIT_SPREAD,
        "BULL",
        spot=100.0,
        quantity=1,
        as_of=FixtureMarketDataAdapter().now,
        iv_rank=42.0,
    )

    assert {leg.expiration_date for leg in selection.legs} == {"2026-06-26"}
    with pytest.raises(ValueError, match="iv_rank"):
        selector.select(
            StrategyType.BULL_CALL_DEBIT_SPREAD,
            "BULL",
            spot=100.0,
            quantity=1,
            as_of=FixtureMarketDataAdapter().now,
            iv_rank=10.0,
        )


def _call(
    expiration: str,
    strike: float,
    delta: float,
    mid: float,
    *,
    open_interest: int = 2_000,
    volume: int = 500,
    spread: float = 0.10,
) -> OptionContractQuote:
    return OptionContractQuote(
        symbol=f"BULL{expiration.replace('-', '')}C{int(strike * 1000):08d}",
        underlying="BULL",
        expiration_date=expiration,
        option_type=OptionType.CALL,
        strike=strike,
        bid=round(mid - spread / 2, 2),
        ask=round(mid + spread / 2, 2),
        last=mid,
        delta=delta,
        gamma=0.03,
        theta=-0.02,
        vega=0.10,
        rho=0.01,
        implied_volatility=0.32,
        volume=volume,
        open_interest=open_interest,
        source="test",
    )
