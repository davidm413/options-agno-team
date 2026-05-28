from options_agno_team.adapters.fixture import FixtureMarketDataAdapter


def test_fixture_adapter_returns_core_market_data() -> None:
    adapter = FixtureMarketDataAdapter()

    bars = adapter.get_bars("SPY", lookback=50)
    quotes = adapter.get_quotes(["SPY"])
    expirations = adapter.get_option_expirations("SPY")
    chain = adapter.get_option_chain("SPY", expiration_date=expirations[0])
    greeks = adapter.get_option_greeks([chain[0].symbol])

    assert len(bars) == 50
    assert quotes["SPY"].last is not None
    assert len(expirations) == 2
    assert any(option.option_type.value == "call" for option in chain)
    assert any(option.option_type.value == "put" for option in chain)
    assert greeks[chain[0].symbol]["delta"] is not None


def test_fixture_stream_invokes_callback() -> None:
    adapter = FixtureMarketDataAdapter()
    seen: list[str] = []

    subscription = adapter.subscribe_prices(["SPY"], lambda quote: seen.append(quote.symbol))

    assert subscription.startswith("fixture-")
    assert seen == ["SPY"]
