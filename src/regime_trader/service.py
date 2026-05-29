from __future__ import annotations

from uuid import uuid4

from regime_trader.config.models import AppConfig
from regime_trader.data.interfaces import BrokerExecutionProvider, MarketDataProvider
from regime_trader.learning.journal import TradeJournal
from regime_trader.regimes.service import RegimeService
from regime_trader.scanner.service import MarketScanner
from regime_trader.schemas.market import Account, Position
from regime_trader.schemas.trading import ExecutionMode, ExecutionRecord, ExecutionRequest
from regime_trader.trading.execution import ExecutionEngine
from regime_trader.trading.risk import RiskEngine
from regime_trader.trading.strategy import StrategyEngine


class DryRunWorkflow:
    def __init__(
        self,
        *,
        config: AppConfig,
        provider: MarketDataProvider,
        execution_provider: BrokerExecutionProvider | None = None,
    ) -> None:
        self.config = config
        self.provider = provider
        self.regimes = RegimeService(config.features, config.regimes)
        self.scanner = MarketScanner(config, provider, self.regimes)
        self.strategies = StrategyEngine(config.strategies)
        self.risk = RiskEngine(config.risk)
        self.execution = ExecutionEngine(config.execution, execution_provider)
        self.journal = TradeJournal()

    def run_symbol(self, symbol: str, *, account: Account, positions: tuple[Position, ...] = ()) -> ExecutionRecord:
        bars = tuple(self.provider.get_bars(symbol, interval="1d", limit=self.config.features.lookback_bars))
        chain = self.provider.get_option_chain(symbol)
        regime = self.regimes.detect(symbol, bars, option_chain=chain)
        proposal = self.strategies.propose(regime, chain, config_version=self.config.version)
        decision = self.risk.review(proposal, account=account, positions=positions)
        preflight = self.execution.run_preflight(proposal) if decision.approved else None
        request = ExecutionRequest(
            request_id=f"dry-run-{uuid4().hex}",
            proposal=proposal,
            risk_decision=decision,
            preflight=preflight,
            mode=ExecutionMode.DRY_RUN,
            idempotency_key=f"idem-{uuid4().hex}",
        )
        execution = self.execution.execute(request)
        self.journal.create(
            regime=regime,
            proposal=proposal,
            risk_decision=decision,
            preflight=preflight,
            execution=execution,
            thesis="deterministic dry-run workflow",
        )
        return execution
