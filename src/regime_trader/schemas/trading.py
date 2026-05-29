from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import Field, field_validator

from regime_trader.schemas.base import StrictModel, ensure_utc, utc_now
from regime_trader.schemas.market import Greeks, OptionType


class StrategyType(StrEnum):
    BULL_CALL_SPREAD = "bull_call_spread"
    BEAR_PUT_SPREAD = "bear_put_spread"
    IRON_CONDOR = "iron_condor"
    LONG_STRADDLE = "long_straddle"
    NO_TRADE = "no_trade"


class OrderAction(StrEnum):
    BUY_TO_OPEN = "buy_to_open"
    SELL_TO_OPEN = "sell_to_open"
    BUY_TO_CLOSE = "buy_to_close"
    SELL_TO_CLOSE = "sell_to_close"


class ExecutionMode(StrEnum):
    DRY_RUN = "dry_run"
    PAPER = "paper"
    LIVE = "live"


class DecisionStatus(StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"
    WARNING = "warning"


class StrategyLeg(StrictModel):
    option_symbol: str
    underlying_symbol: str
    action: OrderAction
    option_type: OptionType
    strike: Decimal = Field(gt=0)
    expiration: datetime
    quantity: int = Field(gt=0)
    price: Decimal | None = Field(default=None, ge=0)
    delta: float | None = None

    @field_validator("expiration")
    @classmethod
    def _expiration_utc(cls, value: datetime) -> datetime:
        return ensure_utc(value)


class StrategyProposal(StrictModel):
    proposal_id: str
    symbol: str
    strategy_type: StrategyType
    created_at: datetime = Field(default_factory=utc_now)
    regime_ref: str
    rationale: tuple[str, ...]
    legs: tuple[StrategyLeg, ...]
    alternatives: tuple[StrategyType, ...] = ()
    pricing_assumptions: dict[str, Decimal] = Field(default_factory=dict)
    max_loss: Decimal | None = Field(default=None, ge=0)
    max_gain: Decimal | None = Field(default=None, ge=0)
    estimated_cost: Decimal | None = None
    exposure_delta: float | None = None
    rejection_reasons: tuple[str, ...] = ()
    config_version: str

    @field_validator("created_at")
    @classmethod
    def _created_at_utc(cls, value: datetime) -> datetime:
        return ensure_utc(value)


class RiskDecision(StrictModel):
    decision_id: str
    proposal_id: str
    status: DecisionStatus
    created_at: datetime = Field(default_factory=utc_now)
    approved_quantity: int = Field(default=0, ge=0)
    reasons: tuple[str, ...]
    evaluated_limits: dict[str, str] = Field(default_factory=dict)
    config_version: str

    @field_validator("created_at")
    @classmethod
    def _created_at_utc(cls, value: datetime) -> datetime:
        return ensure_utc(value)

    @property
    def approved(self) -> bool:
        return self.status == DecisionStatus.APPROVED


class PreflightResult(StrictModel):
    preflight_id: str
    proposal_id: str
    status: DecisionStatus
    estimated_cost: Decimal | None = None
    buying_power_required: Decimal | None = None
    commission: Decimal | None = None
    strategy_name: str | None = None
    validation_messages: tuple[str, ...] = ()
    provider: str
    created_at: datetime = Field(default_factory=utc_now)

    @field_validator("created_at")
    @classmethod
    def _created_at_utc(cls, value: datetime) -> datetime:
        return ensure_utc(value)

    @property
    def approved(self) -> bool:
        return self.status == DecisionStatus.APPROVED


class ExecutionRequest(StrictModel):
    request_id: str
    proposal: StrategyProposal
    risk_decision: RiskDecision
    preflight: PreflightResult | None = None
    mode: ExecutionMode
    idempotency_key: str
    operator_approved: bool = False


class ExecutionRecord(StrictModel):
    execution_id: str
    request_id: str
    proposal_id: str
    mode: ExecutionMode
    status: DecisionStatus
    provider_order_id: str | None = None
    reasons: tuple[str, ...]
    created_at: datetime = Field(default_factory=utc_now)
    provider_response_ref: str | None = None

    @field_validator("created_at")
    @classmethod
    def _created_at_utc(cls, value: datetime) -> datetime:
        return ensure_utc(value)


class MonitoringAlert(StrictModel):
    alert_id: str
    symbol: str
    severity: str
    reason: str
    created_at: datetime = Field(default_factory=utc_now)
    requires_approval: bool = True

    @field_validator("created_at")
    @classmethod
    def _created_at_utc(cls, value: datetime) -> datetime:
        return ensure_utc(value)


class MonitoringSnapshot(StrictModel):
    symbol: str
    timestamp: datetime
    position_status: str
    pnl: Decimal | None = None
    greeks: Greeks | None = None
    recommendation: str = "hold"
    rationale: tuple[str, ...] = ()
    alerts: tuple[MonitoringAlert, ...] = ()

    @field_validator("timestamp")
    @classmethod
    def _timestamp_utc(cls, value: datetime) -> datetime:
        return ensure_utc(value)
