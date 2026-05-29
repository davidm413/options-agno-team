from __future__ import annotations

from typing import Any
from uuid import uuid4

from regime_trader.config.secrets import redact_sensitive
from regime_trader.schemas.events import Event, EventType


class AuditLogger:
    def __init__(self) -> None:
        self.events: list[Event] = []

    def record(
        self,
        event_type: str,
        *,
        payload: dict[str, Any],
        symbol: str | None = None,
        config_version: str | None = None,
    ) -> Event:
        event = Event(
            event_id=f"audit-{uuid4().hex}",
            event_type=EventType.AUDIT,
            symbol=symbol,
            payload={"audit_type": event_type, "payload": redact_sensitive(payload)},
            config_version=config_version,
        )
        self.events.append(event)
        return event
