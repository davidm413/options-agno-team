from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

from options_agno_team.adapters.public import PublicMarketDataAdapter


def test_public_adapter_normalizes_bars_and_calls_sdk_shape() -> None:
    raw_bar = SimpleNamespace(
        timestamp="2026-05-28T14:30:00Z",
        open=100,
        high=102,
        low=99,
        close=101,
        volume=1000,
    )
    client = MagicMock()
    client.get_bars.return_value = SimpleNamespace(
        pre_market=SimpleNamespace(bars=[]),
        regular_market=SimpleNamespace(bars=[raw_bar]),
        after_market=SimpleNamespace(bars=[]),
    )
    adapter = PublicMarketDataAdapter(client=client)

    bars = adapter.get_bars("SPY", lookback=1)

    assert bars[0].symbol == "SPY"
    assert bars[0].close == 101.0
    client.get_bars.assert_called_once()


def test_public_adapter_normalizes_quotes_and_chain() -> None:
    client = MagicMock()
    equity_instrument = SimpleNamespace(symbol="SPY")
    option_instrument = SimpleNamespace(symbol="SPY260626C00520000")
    client.get_quotes.return_value = [
        SimpleNamespace(
            instrument=equity_instrument,
            last_timestamp=datetime(2026, 5, 28, tzinfo=timezone.utc),
            bid=519.9,
            ask=520.1,
            last=520,
            volume=100,
        )
    ]
    client.get_option_expirations.return_value = SimpleNamespace(expirations=["2026-06-26"])
    details = SimpleNamespace(
        strike_price=520,
        greeks=SimpleNamespace(
            delta=0.5,
            gamma=0.1,
            theta=-0.02,
            vega=0.12,
            rho=0.01,
            implied_volatility=0.25,
        ),
    )
    option_quote = SimpleNamespace(
        instrument=option_instrument,
        option_details=details,
        bid=4.9,
        ask=5.1,
        last=5.0,
        volume=10,
        open_interest=100,
    )
    client.get_option_chain.return_value = SimpleNamespace(calls=[option_quote], puts=[])
    adapter = PublicMarketDataAdapter(client=client)

    quote = adapter.get_quotes(["SPY"])["SPY"]
    chain = adapter.get_option_chain("SPY")

    assert quote.mid == 520.0
    assert chain[0].symbol == "SPY260626C00520000"
    assert chain[0].implied_volatility == 0.25
    client.get_option_chain.assert_called_once()
