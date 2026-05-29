from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable

from regime_trader.schemas.events import Event, EventType

EventHandler = Callable[[Event], None]


class EventBus:
    def __init__(self) -> None:
        self._handlers: dict[EventType, list[EventHandler]] = defaultdict(list)
        self.events: list[Event] = []

    def subscribe(self, event_type: EventType, handler: EventHandler) -> None:
        self._handlers[event_type].append(handler)

    def publish(self, event: Event) -> None:
        self.events.append(event)
        for handler in self._handlers[event.event_type]:
            handler(event)
