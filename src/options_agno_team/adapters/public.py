"""Public.com adapter using publicdotcom-py when credentials are available."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from options_agno_team.adapters.base import PriceCallback
from options_agno_team.config import AppConfig
from options_agno_team.models import NormalizedBar, NormalizedQuote, OptionContractQuote, OptionType


class PublicMarketDataAdapter:
    def __init__(self, *, config: AppConfig | None = None, client: Any | None = None) -> None:
        self.config = config or AppConfig.from_env()
        self._sdk: Any | None = None
        self.client = client or self._build_client()

    def get_bars(self, symbol: str, *, lookback: int = 120, interval: str = "1d") -> list[NormalizedBar]:
        period = self._enum("BarPeriod", _period_for_lookback(lookback))
        aggregation = self._enum("BarAggregation", _aggregation_for_interval(interval))
        response = self.client.get_bars(symbol.upper(), period, aggregation=aggregation)
        bars: list[NormalizedBar] = []
        for session_name in ("pre_market", "regular_market", "after_market"):
            session = getattr(response, session_name, None)
            for raw_bar in getattr(session, "bars", []) or []:
                bars.append(
                    NormalizedBar(
                        symbol=symbol.upper(),
                        timestamp=_parse_timestamp(getattr(raw_bar, "timestamp")),
                        open=float(getattr(raw_bar, "open")),
                        high=float(getattr(raw_bar, "high")),
                        low=float(getattr(raw_bar, "low")),
                        close=float(getattr(raw_bar, "close")),
                        volume=float(getattr(raw_bar, "volume")),
                        session=session_name.replace("_market", ""),
                        source="public",
                    )
                )
        return sorted(bars, key=lambda bar: bar.timestamp)[-lookback:]

    def get_quotes(self, symbols: list[str]) -> dict[str, NormalizedQuote]:
        instruments = [self._order_instrument(symbol.upper(), "EQUITY") for symbol in symbols]
        raw_quotes = self.client.get_quotes(instruments)
        quotes: dict[str, NormalizedQuote] = {}
        for quote in raw_quotes:
            instrument = getattr(quote, "instrument")
            symbol = getattr(instrument, "symbol").upper()
            timestamp = getattr(quote, "last_timestamp", None) or datetime.now(timezone.utc)
            quotes[symbol] = NormalizedQuote(
                symbol=symbol,
                timestamp=_parse_timestamp(timestamp),
                bid=_float_or_none(getattr(quote, "bid", None)),
                ask=_float_or_none(getattr(quote, "ask", None)),
                last=_float_or_none(getattr(quote, "last", None)),
                volume=_float_or_none(getattr(quote, "volume", None)),
                source="public",
            )
        return quotes

    def get_option_expirations(self, symbol: str) -> list[str]:
        request = self._option_expirations_request(symbol.upper())
        response = self.client.get_option_expirations(request)
        return list(getattr(response, "expirations"))

    def get_option_chain(
        self, symbol: str, *, expiration_date: str | None = None
    ) -> list[OptionContractQuote]:
        expiration = expiration_date or self.get_option_expirations(symbol)[0]
        request = self._option_chain_request(symbol.upper(), expiration)
        response = self.client.get_option_chain(request)
        return [
            self._normalize_option_quote(symbol.upper(), expiration, raw, OptionType.CALL)
            for raw in getattr(response, "calls", [])
        ] + [
            self._normalize_option_quote(symbol.upper(), expiration, raw, OptionType.PUT)
            for raw in getattr(response, "puts", [])
        ]

    def get_option_greeks(self, osi_symbols: list[str]) -> dict[str, dict[str, float | None]]:
        response = self.client.get_option_greeks(osi_symbols=osi_symbols)
        result: dict[str, dict[str, float | None]] = {}
        for entry in getattr(response, "greeks", []):
            values = getattr(entry, "greeks", None)
            result[getattr(entry, "symbol")] = {
                "delta": _float_or_none(getattr(values, "delta", None)) if values else None,
                "gamma": _float_or_none(getattr(values, "gamma", None)) if values else None,
                "theta": _float_or_none(getattr(values, "theta", None)) if values else None,
                "vega": _float_or_none(getattr(values, "vega", None)) if values else None,
                "rho": _float_or_none(getattr(values, "rho", None)) if values else None,
                "implied_volatility": _float_or_none(
                    getattr(values, "implied_volatility", None)
                )
                if values
                else None,
            }
        return result

    def get_account(self) -> dict[str, Any]:
        accounts = self.client.get_accounts()
        first = next(iter(getattr(accounts, "accounts", []) or []), None)
        portfolio = self.client.get_portfolio()
        return {
            "account_id": getattr(first, "account_id", None),
            "equity": _float_or_none(getattr(portfolio, "equity", None))
            or _float_or_none(getattr(portfolio, "total_value", None))
            or 0.0,
            "buying_power": _float_or_none(getattr(portfolio, "buying_power", None)) or 0.0,
            "portfolio_delta": _float_or_none(getattr(portfolio, "delta", None)) or 0.0,
        }

    def get_positions(self) -> list[dict[str, Any]]:
        portfolio = self.client.get_portfolio()
        positions: list[dict[str, Any]] = []
        for position in getattr(portfolio, "positions", []) or []:
            instrument = getattr(position, "instrument", None)
            positions.append(
                {
                    "symbol": getattr(instrument, "symbol", getattr(position, "symbol", "")),
                    "quantity": _float_or_none(getattr(position, "quantity", None)) or 0.0,
                    "market_value": _float_or_none(getattr(position, "market_value", None)) or 0.0,
                    "delta": _float_or_none(getattr(position, "delta", None)) or 0.0,
                }
            )
        return positions

    def subscribe_prices(
        self, symbols: list[str], callback: PriceCallback, *, interval_seconds: float = 5.0
    ) -> str:
        instruments = [self._order_instrument(symbol.upper(), "EQUITY") for symbol in symbols]

        def on_change(change: Any) -> None:
            quote = getattr(change, "new_quote", change)
            instrument = getattr(quote, "instrument")
            callback(
                NormalizedQuote(
                    symbol=getattr(instrument, "symbol").upper(),
                    timestamp=_parse_timestamp(
                        getattr(quote, "last_timestamp", None) or datetime.now(timezone.utc)
                    ),
                    bid=_float_or_none(getattr(quote, "bid", None)),
                    ask=_float_or_none(getattr(quote, "ask", None)),
                    last=_float_or_none(getattr(quote, "last", None)),
                    volume=_float_or_none(getattr(quote, "volume", None)),
                    source="public",
                )
            )

        config = None
        if self._sdk is not None:
            config = self._sdk.SubscriptionConfig(polling_frequency_seconds=interval_seconds)
        return self.client.price_stream.subscribe(instruments, on_change, config)

    def _build_client(self) -> Any:
        try:
            import public_api_sdk as sdk  # type: ignore[import-not-found]
        except ImportError as exc:
            raise RuntimeError("publicdotcom-py is required for DATA_MODE=public") from exc

        self._sdk = sdk
        if not self.config.public_api_secret_key:
            raise RuntimeError("API_SECRET_KEY is required for DATA_MODE=public")
        return sdk.PublicApiClient(
            sdk.ApiKeyAuthConfig(api_secret_key=self.config.public_api_secret_key),
            config=sdk.PublicApiClientConfiguration(
                default_account_number=self.config.public_default_account_number
            ),
        )

    def _enum(self, class_name: str, member_name: str) -> Any:
        if self._sdk is None:
            return member_name
        return getattr(getattr(self._sdk, class_name), member_name)

    def _order_instrument(self, symbol: str, instrument_type: str) -> Any:
        if self._sdk is None:
            return {"symbol": symbol, "type": instrument_type}
        return self._sdk.OrderInstrument(
            symbol=symbol, type=getattr(self._sdk.InstrumentType, instrument_type)
        )

    def _option_expirations_request(self, symbol: str) -> Any:
        instrument = self._order_instrument(symbol, "EQUITY")
        if self._sdk is None:
            return {"instrument": instrument}
        return self._sdk.OptionExpirationsRequest(instrument=instrument)

    def _option_chain_request(self, symbol: str, expiration: str) -> Any:
        instrument = self._order_instrument(symbol, "EQUITY")
        if self._sdk is None:
            return {"instrument": instrument, "expiration_date": expiration}
        return self._sdk.OptionChainRequest(instrument=instrument, expiration_date=expiration)

    def _normalize_option_quote(
        self, underlying: str, expiration: str, raw: Any, option_type: OptionType
    ) -> OptionContractQuote:
        instrument = getattr(raw, "instrument")
        details = getattr(raw, "option_details", None)
        greeks = getattr(details, "greeks", None) if details else None
        return OptionContractQuote(
            symbol=getattr(instrument, "symbol"),
            underlying=underlying,
            expiration_date=expiration,
            option_type=option_type,
            strike=_float_or_none(getattr(details, "strike_price", None)) or 0.0,
            bid=_float_or_none(getattr(raw, "bid", None)),
            ask=_float_or_none(getattr(raw, "ask", None)),
            last=_float_or_none(getattr(raw, "last", None)),
            delta=_float_or_none(getattr(greeks, "delta", None)) if greeks else None,
            gamma=_float_or_none(getattr(greeks, "gamma", None)) if greeks else None,
            theta=_float_or_none(getattr(greeks, "theta", None)) if greeks else None,
            vega=_float_or_none(getattr(greeks, "vega", None)) if greeks else None,
            rho=_float_or_none(getattr(greeks, "rho", None)) if greeks else None,
            implied_volatility=_float_or_none(getattr(greeks, "implied_volatility", None))
            if greeks
            else None,
            volume=getattr(raw, "volume", None),
            open_interest=getattr(raw, "open_interest", None),
            source="public",
        )


def _period_for_lookback(lookback: int) -> str:
    if lookback <= 1:
        return "DAY"
    if lookback <= 7:
        return "WEEK"
    if lookback <= 31:
        return "MONTH"
    if lookback <= 366:
        return "YEAR"
    return "FIVE_YEARS"


def _aggregation_for_interval(interval: str) -> str:
    mapping = {
        "1m": "ONE_MINUTE",
        "5m": "FIVE_MINUTES",
        "10m": "TEN_MINUTES",
        "15m": "FIFTEEN_MINUTES",
        "30m": "THIRTY_MINUTES",
        "1h": "ONE_HOUR",
        "1d": "ONE_DAY",
    }
    return mapping.get(interval.lower(), "ONE_DAY")


def _parse_timestamp(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    return datetime.now(timezone.utc)


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)
