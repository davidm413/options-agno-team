from __future__ import annotations

from typing import Any
from uuid import uuid4

from pydantic import Field

from regime_trader.schemas.base import StrictModel, utc_now


class StructuredHandoff(StrictModel):
    handoff_id: str = Field(default_factory=lambda: f"handoff-{uuid4().hex}")
    from_agent: str
    to_agent: str
    payload_type: str
    payload: dict[str, Any]
    created_at: str = Field(default_factory=lambda: utc_now().isoformat())


def create_handoff(from_agent: str, to_agent: str, payload_type: str, payload: Any) -> StructuredHandoff:
    model_dump = getattr(payload, "model_dump", None)
    data = model_dump(mode="json") if callable(model_dump) else dict(payload)
    return StructuredHandoff(
        from_agent=from_agent,
        to_agent=to_agent,
        payload_type=payload_type,
        payload=data,
    )
