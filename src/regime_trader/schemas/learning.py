from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import Field, field_validator

from regime_trader.schemas.base import StrictModel, ensure_utc, utc_now
from regime_trader.schemas.trading import ExecutionMode, StrategyType


class ReflectionStatus(StrEnum):
    COMPLETE = "complete"
    INCOMPLETE = "incomplete"


class ApprovalStatus(StrEnum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    REJECTED = "rejected"


class TradeJournalEntry(StrictModel):
    journal_id: str
    symbol: str
    strategy_type: StrategyType
    entry_regime_label: str
    thesis: str
    proposal_id: str
    risk_decision_id: str
    preflight_id: str | None = None
    execution_id: str | None = None
    execution_mode: ExecutionMode
    opened_at: datetime = Field(default_factory=utc_now)
    closed_at: datetime | None = None
    realized_pnl: Decimal | None = None
    monitoring_event_ids: tuple[str, ...] = ()
    audit_event_ids: tuple[str, ...] = ()

    @field_validator("opened_at", "closed_at")
    @classmethod
    def _timestamp_utc(cls, value: datetime | None) -> datetime | None:
        return ensure_utc(value) if value else None


class ReflectionResult(StrictModel):
    reflection_id: str
    journal_id: str
    status: ReflectionStatus
    observations: tuple[str, ...]
    failure_modes: tuple[str, ...] = ()
    improvement_candidates: tuple[str, ...] = ()
    missing_data: tuple[str, ...] = ()
    created_at: datetime = Field(default_factory=utc_now)

    @field_validator("created_at")
    @classmethod
    def _created_at_utc(cls, value: datetime) -> datetime:
        return ensure_utc(value)


class PerformanceMetric(StrictModel):
    group_key: str
    sample_size: int = Field(ge=0)
    win_rate: float | None = Field(default=None, ge=0, le=1)
    average_return: Decimal | None = None
    max_drawdown: Decimal | None = None
    average_holding_hours: float | None = Field(default=None, ge=0)
    risk_adjusted_return: float | None = None
    low_confidence: bool


class LearnedHeuristic(StrictModel):
    heuristic_id: str
    evidence_refs: tuple[str, ...]
    affected_regimes: tuple[str, ...]
    recommendation: str
    proposed_config_change: dict[str, str]
    approval_status: ApprovalStatus = ApprovalStatus.PROPOSED
    created_at: datetime = Field(default_factory=utc_now)

    @field_validator("created_at")
    @classmethod
    def _created_at_utc(cls, value: datetime) -> datetime:
        return ensure_utc(value)


class RetrainingJob(StrictModel):
    job_id: str
    trigger: str
    evidence: tuple[str, ...]
    dataset_scope: str
    status: str = "requested"
    candidate_model_version: str | None = None
    comparison_metrics: dict[str, float] = Field(default_factory=dict)
    rollback_model_version: str | None = None
    approval_status: ApprovalStatus = ApprovalStatus.PROPOSED
