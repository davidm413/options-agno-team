from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import date, datetime
from typing import Protocol

from pydantic import Field

from regime_trader.schemas.base import StrictModel
from regime_trader.schemas.market import Account, Bar, Greeks, OptionChain, Position, Quote
from regime_trader.schemas.trading import ExecutionRecord, PreflightResult, StrategyProposal


class ProviderError(RuntimeError):
    def __init__(self, message: str, *, retryable: bool = False, code: str = "provider_error") -> None:
        super().__init__(message)
        self.retryable = retryable
        self.code = code


class RateLimitError(ProviderError):
    def __init__(self, message: str = "provider rate limit reached", *, retry_after_seconds: float = 1) -> None:
        super().__init__(message, retryable=True, code="rate_limit")
        self.retry_after_seconds = retry_after_seconds


class ProviderStatus(StrictModel):
    provider: str
    healthy: bool
    message: str
    retry_after_seconds: float | None = Field(default=None, ge=0)


class MarketDataProvider(Protocol):
    provider_name: str

    def get_accounts(self) -> Sequence[Account]: ...

    def get_positions(self, account_id: str | None = None) -> Sequence[Position]: ...

    def get_quotes(self, symbols: Sequence[str]) -> Sequence[Quote]: ...

    def get_bars(
        self,
        symbol: str,
        *,
        interval: str,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int | None = None,
    ) -> Sequence[Bar]: ...

    def get_option_expirations(self, symbol: str) -> Sequence[date]: ...

    def get_option_chain(self, symbol: str, expiration: date | None = None) -> OptionChain: ...

    def get_option_greeks(self, option_symbols: Sequence[str]) -> dict[str, Greeks]: ...

    def health(self) -> ProviderStatus: ...


class BrokerExecutionProvider(Protocol):
    provider_name: str

    def preflight_multileg(self, proposal: StrategyProposal, *, account_id: str | None = None) -> PreflightResult: ...

    def place_multileg_order(
        self,
        proposal: StrategyProposal,
        *,
        account_id: str | None = None,
        idempotency_key: str,
    ) -> ExecutionRecord: ...


class StreamingProvider(Protocol):
    provider_name: str

    def stream_quotes(self, symbols: Iterable[str]) -> Iterable[Quote]: ...
