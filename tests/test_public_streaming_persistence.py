from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from regime_trader.config.models import AppConfig
from regime_trader.config.secrets import MissingSecretError
from regime_trader.data.interfaces import ProviderError, RateLimitError
from regime_trader.data.public_adapter import PublicComAdapter
from regime_trader.data.reliability import RetryPolicy, provider_read
from regime_trader.data.streaming import ReconnectPolicy, StreamingSupervisor
from regime_trader.persistence.audit import AuditLogger
from regime_trader.persistence.config_version import ConfigVersionRepository
from regime_trader.persistence.live_state import LiveStateRepository
from regime_trader.persistence.parquet_store import ParquetStore
from regime_trader.schemas.events import EventType
from regime_trader.testing.fixtures import fixture_bars


class FakePublicClient:
    def get_accounts(self) -> dict[str, object]:
        return {"accounts": [{"id": "acct-1", "buying_power": "1000"}]}

    def get_portfolio(self, account_id: str | None = None) -> dict[str, object]:
        return {"positions": [{"symbol": "SPY", "quantity": "1", "type": "equity"}]}

    def get_bars(self, **kwargs: object) -> dict[str, object]:
        return {
            "bars": [
                {
                    "timestamp": datetime(2026, 1, 1, tzinfo=UTC).isoformat(),
                    "open": "100",
                    "high": "101",
                    "low": "99",
                    "close": "100.5",
                    "volume": 100,
                }
            ]
        }

    def get_quotes(self, symbols: list[str]) -> list[dict[str, object]]:
        symbol = getattr(symbols[0], "symbol", symbols[0])
        return [{"symbol": symbol, "bid": "100", "ask": "100.1", "last": "100.05"}]

    def get_option_expirations(self, symbol: str) -> list[str]:
        return ["2026-07-17"]

    def get_option_chain(self, symbol: str, expiration: object | None = None) -> dict[str, object]:
        return {"contracts": []}

    def get_option_greeks(self, symbols: list[str]) -> dict[str, object]:
        return {symbols[0]: {"delta": 0.5}}

    def stream_quotes(self, symbols: list[str]) -> list[dict[str, object]]:
        return [{"symbol": symbols[0], "bid": "100", "ask": "100.2", "last": "100.1"}]


def test_public_adapter_normalizes_mocked_client_and_missing_client_fails() -> None:
    adapter = PublicComAdapter(client=FakePublicClient())
    assert adapter.get_accounts()[0].account_id == "acct-1"
    assert adapter.get_positions()[0].symbol == "SPY"
    assert adapter.get_bars("SPY", interval="1d")[0].close == Decimal("100.5")
    assert adapter.get_quotes(["SPY"])[0].symbol == "SPY"
    assert adapter.get_option_expirations("SPY")[0].isoformat() == "2026-07-17"
    assert adapter.get_option_greeks(["SPY260717C00500000"])["SPY260717C00500000"].delta == 0.5
    assert next(adapter.stream_quotes(["SPY"])).last == Decimal("100.1")
    with pytest.raises(MissingSecretError):
        PublicComAdapter().get_accounts()


def test_rate_limit_retry_and_stream_interruption_health_event() -> None:
    attempts = {"count": 0}

    def flaky_read() -> str:
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise RateLimitError(retry_after_seconds=0)
        return "ok"

    assert provider_read(flaky_read, policy=RetryPolicy(max_retries=1)) == "ok"
    supervisor = StreamingSupervisor("fixture", ReconnectPolicy(attempts=1))
    events = supervisor.run_once(iter([{"type": "quote", "symbol": "SPY"}, RuntimeError("boom")]))
    assert events[0].event_type == EventType.MARKET_UPDATE

    def broken_events() -> object:
        yield {"type": "quote", "symbol": "SPY"}
        raise ProviderError("stream_down")

    health_events = supervisor.run_once(broken_events())
    assert health_events[-1].event_type == EventType.STREAM_HEALTH
    assert health_events[-1].payload["backfill_requested"] is True


def test_persistence_helpers_redact_and_store_versions(tmp_path) -> None:
    config = AppConfig()
    versions = ConfigVersionRepository()
    assert versions.persist(config) == config.version
    live_state = LiveStateRepository(ttl_seconds=60)
    assert live_state.set("regime:SPY", {"status": "ok"}).stale is False
    audit = AuditLogger()
    event = audit.record("provider_error", payload={"api_secret": "abcdef"})
    assert event.payload["payload"]["api_secret"] == "ab***ef"
    parquet_path = ParquetStore(tmp_path).write_bars(fixture_bars(count=5))
    assert parquet_path.exists()
