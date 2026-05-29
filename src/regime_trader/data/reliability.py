from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Generic, TypeVar

from regime_trader.data.interfaces import ProviderError, RateLimitError

T = TypeVar("T")


@dataclass(frozen=True)
class RetryPolicy:
    max_retries: int = 2
    backoff_seconds: float = 0.25
    timeout_seconds: float = 10.0


@dataclass
class CacheEntry(Generic[T]):
    value: T
    stored_at: float
    ttl_seconds: float

    def fresh(self) -> bool:
        return time.time() - self.stored_at <= self.ttl_seconds


class ReadThroughCache(Generic[T]):
    def __init__(self) -> None:
        self._entries: dict[str, CacheEntry[T]] = {}

    def get(self, key: str) -> T | None:
        entry = self._entries.get(key)
        if entry and entry.fresh():
            return entry.value
        return None

    def set(self, key: str, value: T, ttl_seconds: float) -> None:
        self._entries[key] = CacheEntry(value=value, stored_at=time.time(), ttl_seconds=ttl_seconds)


def provider_read(
    operation: Callable[[], T],
    *,
    policy: RetryPolicy,
    cache: ReadThroughCache[T] | None = None,
    cache_key: str | None = None,
    cache_ttl_seconds: float = 0,
    allow_cached: bool = False,
) -> T:
    last_error: Exception | None = None
    for attempt in range(policy.max_retries + 1):
        try:
            value = operation()
            if cache and cache_key and cache_ttl_seconds > 0:
                cache.set(cache_key, value, cache_ttl_seconds)
            return value
        except ProviderError as exc:
            last_error = exc
            if not exc.retryable or attempt >= policy.max_retries:
                break
            retry_after = exc.retry_after_seconds if isinstance(exc, RateLimitError) else None
            time.sleep(retry_after or policy.backoff_seconds * (2**attempt))
    if allow_cached and cache and cache_key:
        cached = cache.get(cache_key)
        if cached is not None:
            return cached
    if last_error:
        raise last_error
    raise ProviderError("provider read failed", retryable=False)
