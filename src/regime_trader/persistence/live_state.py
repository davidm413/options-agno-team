from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import Field

from regime_trader.schemas.base import StrictModel


class LiveStateRecord(StrictModel):
    key: str
    payload: dict[str, Any]
    updated_at: datetime
    ttl_seconds: int = Field(gt=0)

    @property
    def stale(self) -> bool:
        return datetime.now(tz=UTC) - self.updated_at > timedelta(seconds=self.ttl_seconds)


class LiveStateRepository:
    def __init__(self, *, redis_client: Any | None = None, ttl_seconds: int = 120) -> None:
        self.redis_client = redis_client
        self.ttl_seconds = ttl_seconds
        self._memory: dict[str, LiveStateRecord] = {}

    def set(self, key: str, payload: dict[str, Any]) -> LiveStateRecord:
        record = LiveStateRecord(
            key=key,
            payload=payload,
            updated_at=datetime.now(tz=UTC),
            ttl_seconds=self.ttl_seconds,
        )
        if self.redis_client is not None:
            self.redis_client.setex(key, self.ttl_seconds, record.model_dump_json())
        self._memory[key] = record
        return record

    def get(self, key: str) -> LiveStateRecord | None:
        if self.redis_client is not None:
            raw = self.redis_client.get(key)
            if raw:
                return LiveStateRecord.model_validate_json(raw)
        return self._memory.get(key)

    def get_current(self, key: str) -> LiveStateRecord | None:
        record = self.get(key)
        if record is None or record.stale:
            return None
        return record

    def dump_json(self) -> str:
        return json.dumps(
            {key: record.model_dump(mode="json") for key, record in self._memory.items()},
            sort_keys=True,
        )
