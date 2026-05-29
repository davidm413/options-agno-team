from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from regime_trader.schemas.base import ProviderMetadata
from regime_trader.schemas.market import (
    Account,
    AssetClass,
    Bar,
    Greeks,
    OptionChain,
    OptionContract,
    OptionType,
    Position,
    Quote,
)


def raw_get(raw: Any, *names: str, default: Any = None) -> Any:
    for name in names:
        if isinstance(raw, Mapping) and name in raw:
            return raw[name]
        if hasattr(raw, name):
            return getattr(raw, name)
    return default


def parse_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day, tzinfo=UTC)
    if isinstance(value, str):
        normalized = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    return datetime.now(tz=UTC)


def parse_decimal(value: Any, default: str = "0") -> Decimal:
    if value is None:
        return Decimal(default)
    return Decimal(str(value))


def provider_metadata(provider: str, *, cached: bool = False, raw_reference: str | None = None) -> ProviderMetadata:
    return ProviderMetadata(provider=provider, cached=cached, raw_reference=raw_reference)


def normalize_quote(raw: Any, *, provider: str, asset_class: AssetClass = AssetClass.EQUITY) -> Quote:
    symbol = str(raw_get(raw, "symbol", "ticker", default="")).upper()
    return Quote(
        symbol=symbol,
        timestamp=parse_datetime(raw_get(raw, "timestamp", "as_of", "time", default=None)),
        bid=parse_decimal(raw_get(raw, "bid", "bid_price"), "0")
        if raw_get(raw, "bid", "bid_price") is not None
        else None,
        ask=parse_decimal(raw_get(raw, "ask", "ask_price"), "0")
        if raw_get(raw, "ask", "ask_price") is not None
        else None,
        last=parse_decimal(raw_get(raw, "last", "last_price", "price"), "0")
        if raw_get(raw, "last", "last_price", "price") is not None
        else None,
        mark=parse_decimal(raw_get(raw, "mark", "mid"), "0") if raw_get(raw, "mark", "mid") is not None else None,
        asset_class=asset_class,
        provider=provider,
        metadata=provider_metadata(provider),
    )


def normalize_bar(raw: Any, *, provider: str, symbol: str, interval: str) -> Bar:
    return Bar(
        symbol=symbol.upper(),
        timestamp=parse_datetime(raw_get(raw, "timestamp", "time", "date")),
        open=parse_decimal(raw_get(raw, "open", "o")),
        high=parse_decimal(raw_get(raw, "high", "h")),
        low=parse_decimal(raw_get(raw, "low", "l")),
        close=parse_decimal(raw_get(raw, "close", "c")),
        volume=int(raw_get(raw, "volume", "v", default=0) or 0),
        interval=interval,
        provider=provider,
        metadata=provider_metadata(provider),
    )


def normalize_greeks(raw: Any | None) -> Greeks | None:
    if raw is None:
        return None
    return Greeks(
        delta=raw_get(raw, "delta"),
        gamma=raw_get(raw, "gamma"),
        theta=raw_get(raw, "theta"),
        vega=raw_get(raw, "vega"),
        rho=raw_get(raw, "rho"),
    )


def normalize_option_contract(raw: Any, *, provider: str, underlying_symbol: str) -> OptionContract:
    expiration_raw = raw_get(raw, "expiration", "expiration_date", "expiry")
    expiration = expiration_raw if isinstance(expiration_raw, date) else parse_datetime(expiration_raw).date()
    option_type_raw = str(raw_get(raw, "option_type", "type", "put_call", default="call")).lower()
    option_type = OptionType.PUT if "put" in option_type_raw else OptionType.CALL
    option_symbol = str(raw_get(raw, "option_symbol", "symbol", "osi_symbol", default="")).upper()
    return OptionContract(
        underlying_symbol=underlying_symbol.upper(),
        option_symbol=option_symbol,
        expiration=expiration,
        strike=parse_decimal(raw_get(raw, "strike", "strike_price")),
        option_type=option_type,
        bid=parse_decimal(raw_get(raw, "bid"), "0") if raw_get(raw, "bid") is not None else None,
        ask=parse_decimal(raw_get(raw, "ask"), "0") if raw_get(raw, "ask") is not None else None,
        mark=parse_decimal(raw_get(raw, "mark", "mid"), "0") if raw_get(raw, "mark", "mid") is not None else None,
        last=parse_decimal(raw_get(raw, "last", "last_price"), "0")
        if raw_get(raw, "last", "last_price") is not None
        else None,
        volume=raw_get(raw, "volume"),
        open_interest=raw_get(raw, "open_interest", "openInterest"),
        implied_volatility=raw_get(raw, "implied_volatility", "iv"),
        greeks=normalize_greeks(raw_get(raw, "greeks")),
        timestamp=parse_datetime(raw_get(raw, "timestamp", "as_of", default=None)),
        provider=provider,
        metadata=provider_metadata(provider),
    )


def normalize_account(raw: Any, *, provider: str) -> Account:
    return Account(
        account_id=str(raw_get(raw, "account_id", "account_number", "id", default="")),
        provider=provider,
        buying_power=parse_decimal(raw_get(raw, "buying_power", "buyingPower", default=0)),
        cash=parse_decimal(raw_get(raw, "cash"), "0") if raw_get(raw, "cash") is not None else None,
        equity=parse_decimal(raw_get(raw, "equity", "portfolio_value"), "0")
        if raw_get(raw, "equity", "portfolio_value") is not None
        else None,
        metadata=provider_metadata(provider),
    )


def normalize_position(raw: Any, *, provider: str) -> Position:
    symbol = str(raw_get(raw, "symbol", "instrument_symbol", default="")).upper()
    asset_type = str(raw_get(raw, "asset_class", "instrument_type", "type", default="equity")).lower()
    asset_class = AssetClass.OPTION if "option" in asset_type else AssetClass.EQUITY
    return Position(
        symbol=symbol,
        asset_class=asset_class,
        quantity=parse_decimal(raw_get(raw, "quantity", "qty", default=0)),
        average_price=parse_decimal(raw_get(raw, "average_price", "avg_price"), "0")
        if raw_get(raw, "average_price", "avg_price") is not None
        else None,
        mark_price=parse_decimal(raw_get(raw, "mark_price", "market_price"), "0")
        if raw_get(raw, "mark_price", "market_price") is not None
        else None,
        market_value=parse_decimal(raw_get(raw, "market_value"), "0")
        if raw_get(raw, "market_value") is not None
        else None,
        unrealized_pnl=parse_decimal(raw_get(raw, "unrealized_pnl", "unrealizedPL"), "0")
        if raw_get(raw, "unrealized_pnl", "unrealizedPL") is not None
        else None,
        greeks=normalize_greeks(raw_get(raw, "greeks")),
        provider=provider,
        metadata=provider_metadata(provider),
    )


def normalize_option_chain(raw: Any, *, provider: str, symbol: str, expiration: date | None = None) -> OptionChain:
    contracts_raw = raw_get(raw, "contracts", "options", "chain", default=raw)
    contracts_iterable = contracts_raw.values() if isinstance(contracts_raw, Mapping) else contracts_raw or []
    contracts = tuple(
        normalize_option_contract(contract, provider=provider, underlying_symbol=symbol)
        for contract in contracts_iterable
    )
    return OptionChain(
        underlying_symbol=symbol.upper(),
        expiration=expiration,
        timestamp=parse_datetime(raw_get(raw, "timestamp", "as_of", default=None)),
        provider=provider,
        contracts=contracts,
        metadata=provider_metadata(provider),
    )
