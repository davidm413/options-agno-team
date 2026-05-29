from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from regime_trader.data.normalization import (
    normalize_bar,
    normalize_option_contract,
    normalize_quote,
    raw_get,
)
from regime_trader.schemas.events import Event, EventType
from regime_trader.schemas.market import AssetClass


@dataclass(frozen=True)
class ReconnectPolicy:
    attempts: int = 5
    backoff_seconds: float = 1.0
    max_gap_seconds: int = 60


class StreamingEventNormalizer:
    def __init__(self, provider: str) -> None:
        self.provider = provider

    def normalize(self, raw: Any) -> Event:
        payload_type = str(raw_get(raw, "type", "event_type", default="quote")).lower()
        symbol = str(raw_get(raw, "symbol", "underlying_symbol", default="")).upper()
        if payload_type == "bar":
            bar = normalize_bar(
                raw,
                provider=self.provider,
                symbol=symbol,
                interval=str(raw_get(raw, "interval", default="1m")),
            )
            payload = bar.model_dump(mode="json")
            event_type = EventType.MARKET_UPDATE
        elif payload_type == "option":
            contract = normalize_option_contract(raw, provider=self.provider, underlying_symbol=symbol)
            payload = contract.model_dump(mode="json")
            event_type = EventType.MARKET_UPDATE
        elif payload_type == "health":
            payload = {
                "status": raw_get(raw, "status", default="unknown"),
                "provider": self.provider,
            }
            event_type = EventType.STREAM_HEALTH
        else:
            quote = normalize_quote(raw, provider=self.provider, asset_class=AssetClass.EQUITY)
            payload = quote.model_dump(mode="json")
            event_type = EventType.MARKET_UPDATE
        return Event(
            event_id=f"evt-{uuid4().hex}",
            event_type=event_type,
            symbol=symbol or None,
            timestamp=datetime.now(tz=UTC),
            payload={"provider": self.provider, "payload_type": payload_type, "data": payload},
        )


def normalize_stream(raw_events: Iterable[Any], *, provider: str) -> Iterator[Event]:
    normalizer = StreamingEventNormalizer(provider)
    for raw in raw_events:
        yield normalizer.normalize(raw)


class StreamingSupervisor:
    def __init__(self, provider: str, policy: ReconnectPolicy) -> None:
        self.provider = provider
        self.policy = policy
        self.normalizer = StreamingEventNormalizer(provider)

    def run_once(self, raw_events: Iterable[Any]) -> tuple[Event, ...]:
        events: list[Event] = []
        try:
            for raw in raw_events:
                events.append(self.normalizer.normalize(raw))
        except Exception as exc:
            events.append(
                Event(
                    event_id=f"evt-{uuid4().hex}",
                    event_type=EventType.STREAM_HEALTH,
                    timestamp=datetime.now(tz=UTC),
                    payload={
                        "provider": self.provider,
                        "status": "interrupted",
                        "error": str(exc),
                        "backfill_requested": True,
                        "reconnect_attempts": self.policy.attempts,
                    },
                )
            )
        return tuple(events)
