"""Adapter protocols for market data and account data."""

from __future__ import annotations

from typing import Any, Callable, Protocol

from options_agno_team.models import NormalizedBar, NormalizedQuote, OptionContractQuote


PriceCallback = Callable[[NormalizedQuote], None]


class MarketDataAdapter(Protocol):
    def get_bars(self, symbol: str, *, lookback: int = 120, interval: str = "1d") -> list[NormalizedBar]:
        """Return normalized OHLCV bars."""

    def get_quotes(self, symbols: list[str]) -> dict[str, NormalizedQuote]:
        """Return normalized quotes keyed by symbol."""

    def get_option_expirations(self, symbol: str) -> list[str]:
        """Return available option expirations."""

    def get_option_chain(
        self, symbol: str, *, expiration_date: str | None = None
    ) -> list[OptionContractQuote]:
        """Return normalized option contract quotes."""

    def get_option_greeks(self, osi_symbols: list[str]) -> dict[str, dict[str, float | None]]:
        """Return greeks keyed by OSI symbol."""

    def get_account(self) -> dict[str, Any]:
        """Return account-level buying power and equity information."""

    def get_positions(self) -> list[dict[str, Any]]:
        """Return open positions."""

    def subscribe_prices(
        self, symbols: list[str], callback: PriceCallback, *, interval_seconds: float = 5.0
    ) -> str:
        """Subscribe to price updates and return a subscription id."""
