from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from options_agno_team.adapters.fixture import FixtureMarketDataAdapter
from options_agno_team.config import AppConfig, DataMode, ExecutionMode
from options_agno_team.models import OptionContractQuote
from options_agno_team.smoke import run_public_smoke


def test_public_smoke_requires_explicit_env_gate() -> None:
    with pytest.raises(RuntimeError, match="PUBLIC_SMOKE_ENABLED"):
        run_public_smoke(
            "SPY",
            config=AppConfig(data_mode=DataMode.PUBLIC),
            public_client=MagicMock(),
            env={},
        )


def test_public_smoke_exercises_market_account_and_preflight_calls(tmp_path) -> None:
    fixture = FixtureMarketDataAdapter()
    client = MagicMock()
    bars = fixture.get_bars("BULL", lookback=30)
    chain = fixture.get_option_chain("BULL", expiration_date=fixture.get_option_expirations("BULL")[0])
    quote = fixture.get_quotes(["BULL"])["BULL"]

    client.get_bars.return_value = SimpleNamespace(
        pre_market=SimpleNamespace(bars=[]),
        regular_market=SimpleNamespace(
            bars=[
                SimpleNamespace(
                    timestamp=bar.timestamp,
                    open=bar.open,
                    high=bar.high,
                    low=bar.low,
                    close=bar.close,
                    volume=bar.volume,
                )
                for bar in bars
            ]
        ),
        after_market=SimpleNamespace(bars=[]),
    )
    client.get_quotes.return_value = [
        SimpleNamespace(
            instrument=SimpleNamespace(symbol="BULL"),
            last_timestamp=datetime(2026, 5, 28, tzinfo=timezone.utc),
            bid=quote.bid,
            ask=quote.ask,
            last=quote.last,
            volume=quote.volume,
        )
    ]
    client.get_option_expirations.return_value = SimpleNamespace(expirations=[chain[0].expiration_date])
    client.get_option_chain.return_value = SimpleNamespace(
        calls=[_raw_option(option) for option in chain if option.option_type.value == "call"],
        puts=[_raw_option(option) for option in chain if option.option_type.value == "put"],
    )
    client.get_option_greeks.return_value = SimpleNamespace(
        greeks=[
            SimpleNamespace(
                symbol=option.symbol,
                greeks=SimpleNamespace(
                    delta=option.delta,
                    gamma=option.gamma,
                    theta=option.theta,
                    vega=option.vega,
                    rho=option.rho,
                    implied_volatility=option.implied_volatility,
                ),
            )
            for option in chain[:4]
        ]
    )
    client.get_accounts.return_value = SimpleNamespace(
        accounts=[SimpleNamespace(account_id="ACCOUNT-1")]
    )
    client.get_portfolio.return_value = SimpleNamespace(
        equity=100_000,
        buying_power=50_000,
        delta=0.02,
        positions=[],
    )
    client.preflight_call_debit_spread.return_value = {"ok": True}
    client.preflight_put_debit_spread.return_value = {"ok": True}
    client.preflight_put_credit_spread.return_value = {"ok": True}
    client.preflight_call_credit_spread.return_value = {"ok": True}

    result = run_public_smoke(
        "BULL",
        config=AppConfig(
            data_mode=DataMode.PUBLIC,
            execution_mode=ExecutionMode.LIVE,
            enable_live_trading=True,
            live_confirmation=AppConfig.live_confirmation_required,
            live_risk_limits_confirmed=True,
            live_alerting_confirmed=True,
            alert_stdout_enabled=True,
            audit_db_path=str(tmp_path / "audit.sqlite3"),
        ),
        public_client=client,
        env={"PUBLIC_SMOKE_ENABLED": "true"},
    )

    assert result["bars"] == 30
    assert result["option_contracts"] == len(chain)
    assert result["greeks_checked"] == 4
    assert result["risk"]["approved"] is True
    assert result["preflight"]["status"] == "preflighted"
    assert any(method[0].startswith("preflight_") for method in client.method_calls)


def _raw_option(option: OptionContractQuote) -> SimpleNamespace:
    return SimpleNamespace(
        instrument=SimpleNamespace(symbol=option.symbol),
        option_details=SimpleNamespace(
            strike_price=option.strike,
            greeks=SimpleNamespace(
                delta=option.delta,
                gamma=option.gamma,
                theta=option.theta,
                vega=option.vega,
                rho=option.rho,
                implied_volatility=option.implied_volatility,
            ),
        ),
        bid=option.bid,
        ask=option.ask,
        last=option.last,
        volume=option.volume,
        open_interest=option.open_interest,
    )
