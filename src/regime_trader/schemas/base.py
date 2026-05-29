from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


def utc_now() -> datetime:
    return datetime.now(tz=UTC)


def ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


class StrictModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        validate_assignment=True,
        use_enum_values=True,
    )


class ProviderMetadata(StrictModel):
    provider: str
    request_id: str | None = None
    source: str = "live"
    cached: bool = False
    received_at: datetime = Field(default_factory=utc_now)
    latency_ms: float | None = Field(default=None, ge=0)
    raw_reference: str | None = None

    @field_validator("received_at")
    @classmethod
    def _received_at_utc(cls, value: datetime) -> datetime:
        return ensure_utc(value)


class DataQualityIssue(StrictModel):
    code: str
    severity: str = "warning"
    message: str
    symbol: str | None = None
    timestamp: datetime = Field(default_factory=utc_now)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("timestamp")
    @classmethod
    def _timestamp_utc(cls, value: datetime) -> datetime:
        return ensure_utc(value)


class DecisionReference(StrictModel):
    decision_id: str
    config_version: str
    created_at: datetime = Field(default_factory=utc_now)

    @field_validator("created_at")
    @classmethod
    def _created_at_utc(cls, value: datetime) -> datetime:
        return ensure_utc(value)
