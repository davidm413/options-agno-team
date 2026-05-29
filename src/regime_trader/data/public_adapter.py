from __future__ import annotations

from collections.abc import Iterable, Iterator, Sequence
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

from regime_trader.config.models import ProviderConfig
from regime_trader.config.secrets import MissingSecretError, load_secret, redact_sensitive
from regime_trader.data.interfaces import (
    BrokerExecutionProvider,
    MarketDataProvider,
    ProviderError,
    ProviderStatus,
)
from regime_trader.data.normalization import (
    normalize_account,
    normalize_bar,
    normalize_greeks,
    normalize_option_chain,
    normalize_position,
    normalize_quote,
    raw_get,
)
from regime_trader.schemas.market import (
    Account,
    AssetClass,
    Bar,
    Greeks,
    OptionChain,
    Position,
    Quote,
)
from regime_trader.schemas.trading import (
    DecisionStatus,
    ExecutionMode,
    ExecutionRecord,
    PreflightResult,
    StrategyProposal,
)


class PublicComAdapter(MarketDataProvider, BrokerExecutionProvider):
    provider_name = "public"

    def __init__(
        self,
        config: ProviderConfig | None = None,
        *,
        client: Any | None = None,
        account_id: str | None = None,
        api_secret: str | None = None,
    ) -> None:
        self.config = config or ProviderConfig()
        self.account_id = account_id
        self._api_secret = api_secret
        self.client = client
        if self.client is None and (api_secret or account_id):
            self.client = self._build_client(api_secret=api_secret, account_id=account_id)

    def _build_client(self, *, api_secret: str | None, account_id: str | None) -> Any:
        secret = api_secret or load_secret(self.config.api_secret_env)
        if secret is None:
            raise MissingSecretError(f"missing required secret: {self.config.api_secret_env}")
        resolved_account = account_id or load_secret(self.config.account_id_env, required=False)
        try:
            from public_api_sdk import (
                ApiKeyAuthConfig,
                PublicApiClient,
                PublicApiClientConfiguration,
            )
        except Exception as exc:  # pragma: no cover - depends on optional runtime install
            raise ProviderError("publicdotcom-py is not installed", retryable=False) from exc
        return PublicApiClient(
            ApiKeyAuthConfig(api_secret_key=secret),
            config=PublicApiClientConfiguration(default_account_number=resolved_account),
        )

    def _require_client(self) -> Any:
        if self.client is None:
            raise MissingSecretError(
                f"Public.com client unavailable; set {self.config.api_secret_env} before live provider calls"
            )
        return self.client

    def health(self) -> ProviderStatus:
        if self.client is None:
            return ProviderStatus(provider=self.provider_name, healthy=False, message="client_not_configured")
        return ProviderStatus(provider=self.provider_name, healthy=True, message="configured")

    def get_accounts(self) -> Sequence[Account]:
        raw = self._require_client().get_accounts()
        accounts = raw_get(raw, "accounts", default=raw)
        return tuple(normalize_account(account, provider=self.provider_name) for account in accounts)

    def get_positions(self, account_id: str | None = None) -> Sequence[Position]:
        raw = self._require_client().get_portfolio(account_id=account_id or self.account_id)
        positions = raw_get(raw, "positions", "holdings", default=[])
        return tuple(normalize_position(position, provider=self.provider_name) for position in positions)

    def get_quotes(self, symbols: Sequence[str]) -> Sequence[Quote]:
        client = self._require_client()
        try:
            from public_api_sdk import InstrumentType, OrderInstrument

            instruments = [OrderInstrument(symbol=symbol, type=InstrumentType.EQUITY) for symbol in symbols]
            raw_quotes = client.get_quotes(instruments)
        except Exception:
            raw_quotes = client.get_quotes(list(symbols))
        return tuple(
            normalize_quote(quote, provider=self.provider_name, asset_class=AssetClass.EQUITY) for quote in raw_quotes
        )

    def stream_quotes(self, symbols: Iterable[str]) -> Iterator[Quote]:
        client = self._require_client()
        if hasattr(client, "stream_quotes"):
            raw_stream = client.stream_quotes(list(symbols))
        elif hasattr(client, "subscribe_prices"):
            raw_stream = client.subscribe_prices(list(symbols))
        else:
            raise ProviderError("public_streaming_not_supported_by_client", retryable=False)
        for raw in raw_stream:
            yield normalize_quote(raw, provider=self.provider_name, asset_class=AssetClass.EQUITY)

    def get_bars(
        self,
        symbol: str,
        *,
        interval: str,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int | None = None,
    ) -> Sequence[Bar]:
        raw = self._require_client().get_bars(symbol=symbol, interval=interval, start=start, end=end, limit=limit)
        bars = raw_get(raw, "bars", "data", default=raw)
        return tuple(normalize_bar(bar, provider=self.provider_name, symbol=symbol, interval=interval) for bar in bars)

    def get_option_expirations(self, symbol: str) -> Sequence[date]:
        raw = self._require_client().get_option_expirations(symbol)
        expirations = raw_get(raw, "expirations", "expiration_dates", default=raw)
        return tuple(
            expiration if isinstance(expiration, date) else datetime.fromisoformat(str(expiration)).date()
            for expiration in expirations
        )

    def get_option_chain(self, symbol: str, expiration: date | None = None) -> OptionChain:
        raw = self._require_client().get_option_chain(symbol, expiration=expiration)
        return normalize_option_chain(raw, provider=self.provider_name, symbol=symbol, expiration=expiration)

    def get_option_greeks(self, option_symbols: Sequence[str]) -> dict[str, Greeks]:
        raw = self._require_client().get_option_greeks(list(option_symbols))
        values = raw_get(raw, "greeks", default=raw)
        if isinstance(values, dict):
            return {symbol: normalize_greeks(item) or Greeks() for symbol, item in values.items()}
        return {str(raw_get(item, "symbol", "option_symbol")): normalize_greeks(item) or Greeks() for item in values}

    def preflight_multileg(self, proposal: StrategyProposal, *, account_id: str | None = None) -> PreflightResult:
        raw = self._require_client().perform_multi_leg_preflight_calculation(
            proposal.model_dump(mode="json"), account_id=account_id or self.account_id
        )
        messages = raw_get(raw, "validation_messages", "messages", default=[])
        approved = bool(raw_get(raw, "approved", "valid", default=not messages))
        return PreflightResult(
            preflight_id=f"preflight-{uuid4().hex}",
            proposal_id=proposal.proposal_id,
            status=DecisionStatus.APPROVED if approved else DecisionStatus.REJECTED,
            estimated_cost=Decimal(str(raw_get(raw, "estimated_cost", "estimatedCost", default=0))),
            buying_power_required=Decimal(str(raw_get(raw, "buying_power_required", "buyingPowerRequired", default=0))),
            commission=Decimal(str(raw_get(raw, "commission", default=0))),
            strategy_name=str(raw_get(raw, "strategy_name", default=proposal.strategy_type)),
            validation_messages=tuple(str(message) for message in messages),
            provider=self.provider_name,
        )

    def place_multileg_order(
        self,
        proposal: StrategyProposal,
        *,
        account_id: str | None = None,
        idempotency_key: str,
    ) -> ExecutionRecord:
        raw = self._require_client().place_multileg_order(
            proposal.model_dump(mode="json"),
            account_id=account_id or self.account_id,
            idempotency_key=idempotency_key,
        )
        provider_order_id = raw_get(raw, "order_id", "id")
        return ExecutionRecord(
            execution_id=f"exec-{uuid4().hex}",
            request_id=idempotency_key,
            proposal_id=proposal.proposal_id,
            mode=ExecutionMode.LIVE,
            status=DecisionStatus.APPROVED,
            provider_order_id=str(provider_order_id) if provider_order_id else None,
            reasons=("provider_order_submitted",),
            provider_response_ref=str(redact_sensitive(raw)),
        )
