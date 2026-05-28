"""Application service orchestration."""

from __future__ import annotations

from typing import Any

from options_agno_team.adapters import FixtureMarketDataAdapter, MarketDataAdapter, PublicMarketDataAdapter
from options_agno_team.config import AppConfig, DataMode
from options_agno_team.execution import ExecutionGateway, ProposalRepository
from options_agno_team.features import FeatureEngine
from options_agno_team.models import (
    ExecutionResult,
    RegimeSnapshot,
    RiskDecision,
    StrategyProposal,
)
from options_agno_team.regime import RegimeEngine
from options_agno_team.risk import RiskEngine
from options_agno_team.strategy import StrategyEngine


class TradingSystem:
    def __init__(
        self,
        *,
        config: AppConfig,
        adapter: MarketDataAdapter,
        feature_engine: FeatureEngine | None = None,
        regime_engine: RegimeEngine | None = None,
        strategy_engine: StrategyEngine | None = None,
        risk_engine: RiskEngine | None = None,
        execution_gateway: ExecutionGateway | None = None,
        repository: ProposalRepository | None = None,
    ) -> None:
        self.config = config
        self.adapter = adapter
        self.feature_engine = feature_engine or FeatureEngine()
        self.regime_engine = regime_engine or RegimeEngine()
        self.strategy_engine = strategy_engine or StrategyEngine(adapter, config)
        self.risk_engine = risk_engine or RiskEngine(adapter, config)
        self.execution_gateway = execution_gateway or ExecutionGateway(config=config)
        self.repository = repository or ProposalRepository()

    def detect_regime(self, symbol: str, *, lookback: int = 120) -> RegimeSnapshot:
        bars = self.adapter.get_bars(symbol, lookback=lookback)
        chain = self.adapter.get_option_chain(symbol)
        features = self.feature_engine.build(symbol, bars, option_chain=chain)
        return self.regime_engine.classify(features)

    def scan_market(self, symbols: list[str] | None = None, *, lookback: int = 120) -> list[RegimeSnapshot]:
        universe = symbols or list(self.config.default_symbols)
        regimes = [self.detect_regime(symbol, lookback=lookback) for symbol in universe]
        return sorted(regimes, key=lambda item: item.confidence, reverse=True)

    def propose_options_strategy(self, symbol: str, *, lookback: int = 120) -> StrategyProposal:
        regime = self.detect_regime(symbol, lookback=lookback)
        proposal = self.strategy_engine.propose(regime)
        self.repository.save_proposal(proposal)
        return proposal

    def check_portfolio_risk(self, proposal_id: str) -> RiskDecision:
        proposal = self.repository.get_proposal(proposal_id)
        decision = self.risk_engine.evaluate(proposal)
        self.repository.save_risk_decision(decision)
        return decision

    def preflight_strategy(self, proposal_id: str) -> ExecutionResult:
        proposal = self.repository.get_proposal(proposal_id)
        risk = self._risk_for(proposal)
        return self.execution_gateway.preflight(proposal, risk)

    def execute_strategy(self, proposal_id: str) -> ExecutionResult:
        proposal = self.repository.get_proposal(proposal_id)
        risk = self._risk_for(proposal)
        return self.execution_gateway.execute(proposal, risk)

    def _risk_for(self, proposal: StrategyProposal) -> RiskDecision:
        if proposal.proposal_id not in self.repository.risk_decisions:
            self.repository.save_risk_decision(self.risk_engine.evaluate(proposal))
        return self.repository.get_risk_decision(proposal.proposal_id)


def build_system(config: AppConfig | None = None, *, public_client: Any | None = None) -> TradingSystem:
    cfg = config or AppConfig.from_env()
    if cfg.data_mode is DataMode.PUBLIC:
        adapter: MarketDataAdapter = PublicMarketDataAdapter(config=cfg, client=public_client)
    else:
        adapter = FixtureMarketDataAdapter()
    gateway = ExecutionGateway(config=cfg, public_client=public_client)
    return TradingSystem(config=cfg, adapter=adapter, execution_gateway=gateway)
