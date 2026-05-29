from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import Field, field_validator

from regime_trader.schemas.base import StrictModel, ensure_utc, utc_now


class EventType(StrEnum):
    MARKET_UPDATE = "market_update"
    FEATURE_UPDATE = "feature_update"
    REGIME_SHIFT = "regime_shift"
    SCAN_RESULT = "scan_result"
    RISK_BREACH = "risk_breach"
    EXECUTION_STATUS = "execution_status"
    LEARNING_EVENT = "learning_event"
    STREAM_HEALTH = "stream_health"
    AUDIT = "audit"


class Event(StrictModel):
    event_id: str
    event_type: EventType
    symbol: str | None = None
    timestamp: datetime = Field(default_factory=utc_now)
    payload: dict[str, Any]
    config_version: str | None = None

    @field_validator("timestamp")
    @classmethod
    def _timestamp_utc(cls, value: datetime) -> datetime:
        return ensure_utc(value)
