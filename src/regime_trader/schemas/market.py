from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import Field, field_validator, model_validator

from regime_trader.schemas.base import DataQualityIssue, ProviderMetadata, StrictModel, ensure_utc


class AssetClass(StrEnum):
    EQUITY = "equity"
    ETF = "etf"
    OPTION = "option"
    CRYPTO = "crypto"


class OptionType(StrEnum):
    CALL = "call"
    PUT = "put"


class Bar(StrictModel):
    symbol: str
    timestamp: datetime
    open: Decimal = Field(gt=0)
    high: Decimal = Field(gt=0)
    low: Decimal = Field(gt=0)
    close: Decimal = Field(gt=0)
    volume: int = Field(ge=0)
    interval: str
    provider: str
    metadata: ProviderMetadata

    @field_validator("timestamp")
    @classmethod
    def _timestamp_utc(cls, value: datetime) -> datetime:
        return ensure_utc(value)

    @model_validator(mode="after")
    def _prices_are_ordered(self) -> Bar:
        if self.high < max(self.open, self.close) or self.low > min(self.open, self.close):
            raise ValueError("bar high/low must bound open and close")
        return self


class Quote(StrictModel):
    symbol: str
    timestamp: datetime
    bid: Decimal | None = Field(default=None, ge=0)
    ask: Decimal | None = Field(default=None, ge=0)
    last: Decimal | None = Field(default=None, ge=0)
    mark: Decimal | None = Field(default=None, ge=0)
    asset_class: AssetClass
    provider: str
    metadata: ProviderMetadata

    @field_validator("timestamp")
    @classmethod
    def _timestamp_utc(cls, value: datetime) -> datetime:
        return ensure_utc(value)


class Greeks(StrictModel):
    delta: float | None = None
    gamma: float | None = None
    theta: float | None = None
    vega: float | None = None
    rho: float | None = None


class OptionContract(StrictModel):
    underlying_symbol: str
    option_symbol: str
    expiration: date
    strike: Decimal = Field(gt=0)
    option_type: OptionType
    bid: Decimal | None = Field(default=None, ge=0)
    ask: Decimal | None = Field(default=None, ge=0)
    mark: Decimal | None = Field(default=None, ge=0)
    last: Decimal | None = Field(default=None, ge=0)
    volume: int | None = Field(default=None, ge=0)
    open_interest: int | None = Field(default=None, ge=0)
    implied_volatility: float | None = Field(default=None, ge=0)
    greeks: Greeks | None = None
    timestamp: datetime
    provider: str
    metadata: ProviderMetadata

    @field_validator("timestamp")
    @classmethod
    def _timestamp_utc(cls, value: datetime) -> datetime:
        return ensure_utc(value)

    @property
    def mid_price(self) -> Decimal | None:
        if self.mark is not None:
            return self.mark
        if self.bid is not None and self.ask is not None:
            return (self.bid + self.ask) / Decimal("2")
        return self.last

    @property
    def spread_width(self) -> Decimal | None:
        if self.bid is None or self.ask is None:
            return None
        return self.ask - self.bid


class OptionChain(StrictModel):
    underlying_symbol: str
    expiration: date | None = None
    timestamp: datetime
    provider: str
    contracts: tuple[OptionContract, ...]
    quality_issues: tuple[DataQualityIssue, ...] = ()
    metadata: ProviderMetadata

    @field_validator("timestamp")
    @classmethod
    def _timestamp_utc(cls, value: datetime) -> datetime:
        return ensure_utc(value)


class Account(StrictModel):
    account_id: str
    provider: str
    buying_power: Decimal = Field(ge=0)
    cash: Decimal | None = Field(default=None, ge=0)
    equity: Decimal | None = Field(default=None, ge=0)
    currency: str = "USD"
    metadata: ProviderMetadata


class Position(StrictModel):
    symbol: str
    asset_class: AssetClass
    quantity: Decimal
    average_price: Decimal | None = Field(default=None, ge=0)
    mark_price: Decimal | None = Field(default=None, ge=0)
    market_value: Decimal | None = None
    unrealized_pnl: Decimal | None = None
    greeks: Greeks | None = None
    provider: str
    metadata: ProviderMetadata
