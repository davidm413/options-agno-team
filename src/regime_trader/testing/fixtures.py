from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from regime_trader.config.models import AppConfig
from regime_trader.data.interfaces import (
    BrokerExecutionProvider,
    MarketDataProvider,
    ProviderStatus,
)
from regime_trader.schemas.base import ProviderMetadata
from regime_trader.schemas.market import (
    Account,
    AssetClass,
    Bar,
    Greeks,
    OptionChain,
    OptionContract,
    OptionType,
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


def fixture_metadata(provider: str = "fixture") -> ProviderMetadata:
    return ProviderMetadata(provider=provider, source="fixture")


def fixture_bars(symbol: str = "SPY", count: int = 40) -> tuple[Bar, ...]:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    bars: list[Bar] = []
    price = Decimal("480")
    for index in range(count):
        price += Decimal("0.80") + (Decimal(index % 3) * Decimal("0.05"))
        timestamp = start + timedelta(days=index)
        bars.append(
            Bar(
                symbol=symbol,
                timestamp=timestamp,
                open=price - Decimal("0.50"),
                high=price + Decimal("1.00"),
                low=price - Decimal("1.20"),
                close=price,
                volume=1_000_000 + index,
                interval="1d",
                provider="fixture",
                metadata=fixture_metadata(),
            )
        )
    return tuple(bars)


def fixture_option_chain(symbol: str = "SPY") -> OptionChain:
    expiration = date(2026, 7, 17)
    timestamp = datetime(2026, 5, 29, 15, 30, tzinfo=UTC)
    contracts = []
    for strike in (Decimal("500"), Decimal("505"), Decimal("510")):
        contracts.append(
            OptionContract(
                underlying_symbol=symbol,
                option_symbol=f"{symbol}{expiration:%y%m%d}C{int(strike):08d}",
                expiration=expiration,
                strike=strike,
                option_type=OptionType.CALL,
                bid=Decimal("4.90") - (strike - Decimal("500")) / Decimal("10"),
                ask=Decimal("5.10") - (strike - Decimal("500")) / Decimal("10"),
                mark=Decimal("5.00") - (strike - Decimal("500")) / Decimal("10"),
                volume=100,
                open_interest=500,
                implied_volatility=0.22,
                greeks=Greeks(delta=0.55),
                timestamp=timestamp,
                provider="fixture",
                metadata=fixture_metadata(),
            )
        )
        contracts.append(
            OptionContract(
                underlying_symbol=symbol,
                option_symbol=f"{symbol}{expiration:%y%m%d}P{int(strike):08d}",
                expiration=expiration,
                strike=strike,
                option_type=OptionType.PUT,
                bid=Decimal("4.80"),
                ask=Decimal("5.00"),
                mark=Decimal("4.90"),
                volume=100,
                open_interest=500,
                implied_volatility=0.24,
                greeks=Greeks(delta=-0.45),
                timestamp=timestamp,
                provider="fixture",
                metadata=fixture_metadata(),
            )
        )
    return OptionChain(
        underlying_symbol=symbol,
        expiration=expiration,
        timestamp=timestamp,
        provider="fixture",
        contracts=tuple(contracts),
        metadata=fixture_metadata(),
    )


def fixture_account() -> Account:
    return Account(
        account_id="acct-fixture",
        provider="fixture",
        buying_power=Decimal("100000"),
        cash=Decimal("100000"),
        equity=Decimal("100000"),
        metadata=fixture_metadata(),
    )


class FixtureProvider(MarketDataProvider, BrokerExecutionProvider):
    provider_name = "fixture"

    def __init__(self, config: AppConfig | None = None) -> None:
        self.config = config or AppConfig()

    def get_accounts(self) -> Sequence[Account]:
        return (fixture_account(),)

    def get_positions(self, account_id: str | None = None) -> Sequence[Position]:
        return ()

    def get_quotes(self, symbols: Sequence[str]) -> Sequence[Quote]:
        return tuple(
            Quote(
                symbol=symbol,
                timestamp=datetime(2026, 2, 15, 15, 30, tzinfo=UTC),
                bid=Decimal("500"),
                ask=Decimal("500.05"),
                last=Decimal("500.02"),
                mark=Decimal("500.025"),
                asset_class=AssetClass.EQUITY,
                provider="fixture",
                metadata=fixture_metadata(),
            )
            for symbol in symbols
        )

    def get_bars(
        self,
        symbol: str,
        *,
        interval: str,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int | None = None,
    ) -> Sequence[Bar]:
        bars = fixture_bars(
            symbol,
            count=max(limit or self.config.features.lookback_bars, self.config.features.lookback_bars),
        )
        return bars[-limit:] if limit else bars

    def get_option_expirations(self, symbol: str) -> Sequence[date]:
        return (date(2026, 7, 17),)

    def get_option_chain(self, symbol: str, expiration: date | None = None) -> OptionChain:
        return fixture_option_chain(symbol).model_copy(update={"timestamp": datetime.now(tz=UTC)})

    def get_option_greeks(self, option_symbols: Sequence[str]) -> dict[str, Greeks]:
        return {symbol: Greeks(delta=0.5) for symbol in option_symbols}

    def health(self) -> ProviderStatus:
        return ProviderStatus(provider=self.provider_name, healthy=True, message="fixture")

    def preflight_multileg(self, proposal: StrategyProposal, *, account_id: str | None = None) -> PreflightResult:
        return PreflightResult(
            preflight_id="preflight-fixture",
            proposal_id=proposal.proposal_id,
            status=DecisionStatus.APPROVED,
            estimated_cost=proposal.estimated_cost,
            buying_power_required=proposal.max_loss,
            commission=Decimal("0"),
            strategy_name=str(proposal.strategy_type),
            provider=self.provider_name,
        )

    def place_multileg_order(
        self,
        proposal: StrategyProposal,
        *,
        account_id: str | None = None,
        idempotency_key: str,
    ) -> ExecutionRecord:
        return ExecutionRecord(
            execution_id="exec-fixture-live",
            request_id=idempotency_key,
            proposal_id=proposal.proposal_id,
            mode=ExecutionMode.LIVE,
            status=DecisionStatus.APPROVED,
            provider_order_id="fixture-order",
            reasons=("fixture_order_submitted",),
        )
