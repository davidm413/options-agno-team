"""Application service orchestration."""

from __future__ import annotations

from typing import Any

from options_agno_team.alerts import AlertDispatcher
from options_agno_team.adapters import FixtureMarketDataAdapter, MarketDataAdapter, PublicMarketDataAdapter
from options_agno_team.backtesting import BacktestService
from options_agno_team.config import AppConfig, DataMode, ExecutionMode
from options_agno_team.execution import ExecutionGateway, ProposalRepository
from options_agno_team.features import FeatureEngine
from options_agno_team.learning import LearningService
from options_agno_team.models import (
    AlertSeverity,
    BacktestReport,
    ExecutionResult,
    ExecutionStatus,
    LearningReport,
    LiveReadinessReport,
    MonitoringEvent,
    PaperPosition,
    RankedTradeCandidate,
    RegimeSnapshot,
    RiskDecision,
    StrategyProposal,
)
from options_agno_team.monitoring import MonitoringService
from options_agno_team.paper import PaperTradingService
from options_agno_team.readiness import evaluate_live_readiness
from options_agno_team.regime import RegimeEngine
from options_agno_team.risk import RiskEngine
from options_agno_team.storage import SQLiteAuditRepository
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
        paper_trading: PaperTradingService | None = None,
        alert_dispatcher: AlertDispatcher | None = None,
    ) -> None:
        self.config = config
        self.adapter = adapter
        self.feature_engine = feature_engine or FeatureEngine()
        self.regime_engine = regime_engine or RegimeEngine()
        self.strategy_engine = strategy_engine or StrategyEngine(adapter, config)
        self.risk_engine = risk_engine or RiskEngine(adapter, config)
        self.execution_gateway = execution_gateway or ExecutionGateway(config=config)
        self.repository = repository or ProposalRepository()
        self.paper_trading = paper_trading or PaperTradingService(adapter, self.repository)
        self.alerting = alert_dispatcher or AlertDispatcher(self.repository, config)
        self.backtesting = BacktestService(
            adapter,
            config,
            feature_engine=self.feature_engine,
            regime_engine=self.regime_engine,
        )
        self.monitoring = MonitoringService(
            adapter,
            self.repository,
            self.paper_trading,
            config,
            feature_engine=self.feature_engine,
            regime_engine=self.regime_engine,
        )
        self.learning = LearningService(
            adapter,
            self.repository,
            feature_engine=self.feature_engine,
            regime_engine=self.regime_engine,
        )

    def detect_regime(self, symbol: str, *, lookback: int = 120) -> RegimeSnapshot:
        bars = self.adapter.get_bars(symbol, lookback=lookback)
        chain = self.adapter.get_option_chain(symbol)
        features = self.feature_engine.build(symbol, bars, option_chain=chain)
        snapshot = self.regime_engine.classify(features)
        self.repository.save_regime_snapshot(snapshot)
        return snapshot

    def scan_market(self, symbols: list[str] | None = None, *, lookback: int = 120) -> list[RegimeSnapshot]:
        universe = symbols or list(self.config.default_symbols)
        regimes = [self.detect_regime(symbol, lookback=lookback) for symbol in universe]
        return sorted(regimes, key=lambda item: item.confidence, reverse=True)

    def propose_options_strategy(self, symbol: str, *, lookback: int = 120) -> StrategyProposal:
        regime = self.detect_regime(symbol, lookback=lookback)
        proposal = self.strategy_engine.propose(regime)
        self.repository.save_proposal(proposal)
        return proposal

    def rank_trade_candidates(
        self, symbols: list[str] | None = None, *, lookback: int = 120
    ) -> list[RankedTradeCandidate]:
        universe = symbols or list(self.config.default_symbols)
        scored: list[tuple[float, StrategyProposal, RiskDecision]] = []
        for symbol in universe:
            proposal = self.propose_options_strategy(symbol, lookback=lookback)
            risk = self.check_portfolio_risk(proposal.proposal_id)
            scored.append((_candidate_score(proposal, risk, self.config), proposal, risk))

        scored.sort(
            key=lambda item: (
                item[2].approved,
                item[0],
                item[1].regime.confidence,
                item[1].symbol,
            ),
            reverse=True,
        )
        return [
            RankedTradeCandidate(
                rank=index,
                symbol=proposal.symbol,
                score=score,
                proposal_id=proposal.proposal_id,
                strategy_type=proposal.strategy_type,
                volatility_regime=proposal.regime.volatility_regime,
                directional_bias=proposal.regime.directional_bias,
                regime_label=proposal.regime.regime_label,
                confidence=proposal.regime.confidence,
                risk_status=risk.status,
                risk_reasons=risk.reasons,
                max_loss=proposal.max_loss,
                risk_budget=risk.risk_budget,
                is_live_capable=proposal.is_live_capable,
                rationale=proposal.rationale,
            )
            for index, (score, proposal, risk) in enumerate(scored, start=1)
        ]

    def check_portfolio_risk(self, proposal_id: str) -> RiskDecision:
        proposal = self.repository.get_proposal(proposal_id)
        decision = self.risk_engine.evaluate(proposal)
        self.repository.save_risk_decision(decision)
        if not decision.approved:
            self.alerting.publish(
                AlertSeverity.WARNING,
                "risk_rejected",
                "Risk check rejected a trade proposal",
                proposal_id=proposal.proposal_id,
                symbol=proposal.symbol,
                payload={
                    "reasons": list(decision.reasons),
                    "max_loss": decision.max_loss,
                    "risk_budget": decision.risk_budget,
                },
            )
        return decision

    def live_readiness(self) -> LiveReadinessReport:
        return evaluate_live_readiness(self.config)

    def preflight_strategy(self, proposal_id: str) -> ExecutionResult:
        proposal = self.repository.get_proposal(proposal_id)
        risk = self._risk_for(proposal)
        result = self.execution_gateway.preflight(proposal, risk)
        self.repository.save_execution_result(result)
        self._alert_execution_result(proposal, result, phase="preflight")
        return result

    def execute_strategy(self, proposal_id: str) -> ExecutionResult:
        proposal = self.repository.get_proposal(proposal_id)
        risk = self._risk_for(proposal)
        result = self.execution_gateway.execute(proposal, risk)
        self.repository.save_execution_result(result)
        self.paper_trading.open_from_dry_run(proposal, result)
        self._alert_execution_result(proposal, result, phase="execute")
        return result

    def list_paper_positions(self, *, open_only: bool = True) -> list[PaperPosition]:
        return self.paper_trading.list_positions(open_only=open_only)

    def mark_to_market(self) -> list[PaperPosition]:
        return self.paper_trading.mark_to_market()

    def run_backtest(
        self,
        symbols: list[str] | None = None,
        *,
        lookback: int = 180,
        min_lookback: int = 60,
        holding_period: int = 10,
        step: int = 5,
    ) -> BacktestReport:
        universe = symbols or list(self.config.default_symbols)
        report = self.backtesting.run(
            universe,
            lookback=lookback,
            min_lookback=min_lookback,
            holding_period=holding_period,
            step=step,
        )
        self.repository.save_backtest_report(report)
        return report

    def monitor_paper_positions(self) -> list[MonitoringEvent]:
        events = self.monitoring.run_once()
        self._alert_monitoring_events(events)
        return events

    def monitor_paper_positions_loop(
        self,
        *,
        iterations: int = 3,
        interval_seconds: float = 60.0,
    ) -> list[list[MonitoringEvent]]:
        batches = self.monitoring.run_loop(iterations=iterations, interval_seconds=interval_seconds)
        for events in batches:
            self._alert_monitoring_events(events)
        return batches

    def reflect_trades(self, *, open_only: bool = True) -> LearningReport:
        return self.learning.reflect_positions(open_only=open_only)

    def _risk_for(self, proposal: StrategyProposal) -> RiskDecision:
        try:
            return self.repository.get_risk_decision(proposal.proposal_id)
        except KeyError:
            decision = self.risk_engine.evaluate(proposal)
            self.repository.save_risk_decision(decision)
            return decision

    def _alert_monitoring_events(self, events: list[MonitoringEvent]) -> None:
        for event in events:
            if event.action == "exit_review":
                self.alerting.publish(
                    AlertSeverity.WARNING,
                    "monitoring_exit_review",
                    "Monitoring detected exit-review triggers",
                    proposal_id=event.proposal_id,
                    symbol=event.symbol,
                    payload={
                        "position_id": event.position_id,
                        "triggers": list(event.triggers),
                        "unrealized_pnl": event.unrealized_pnl,
                        "pnl_pct_of_risk": event.pnl_pct_of_risk,
                    },
                )

    def _alert_execution_result(
        self,
        proposal: StrategyProposal,
        result: ExecutionResult,
        *,
        phase: str,
    ) -> None:
        if result.status is ExecutionStatus.REJECTED:
            self.alerting.publish(
                AlertSeverity.WARNING,
                "execution_rejected",
                f"{phase} rejected",
                proposal_id=proposal.proposal_id,
                symbol=proposal.symbol,
                payload={"status": result.status.value, "message": result.message},
            )
        elif result.status is ExecutionStatus.PLACED:
            self.alerting.publish(
                AlertSeverity.CRITICAL,
                "live_order_placed",
                "Live order submitted",
                proposal_id=proposal.proposal_id,
                symbol=proposal.symbol,
                payload={"order_id": result.order_id, "status": result.status.value},
            )
        elif result.status is ExecutionStatus.PREFLIGHTED and self.config.execution_mode is ExecutionMode.LIVE:
            self.alerting.publish(
                AlertSeverity.INFO,
                "live_preflighted",
                "Live preflight succeeded",
                proposal_id=proposal.proposal_id,
                symbol=proposal.symbol,
                payload={"status": result.status.value},
            )


def build_system(config: AppConfig | None = None, *, public_client: Any | None = None) -> TradingSystem:
    cfg = config or AppConfig.from_env()
    gateway_client = public_client
    if cfg.data_mode is DataMode.PUBLIC:
        public_adapter = PublicMarketDataAdapter(config=cfg, client=public_client)
        adapter: MarketDataAdapter = public_adapter
        gateway_client = public_adapter.client
    else:
        adapter = FixtureMarketDataAdapter()
    gateway = ExecutionGateway(config=cfg, public_client=gateway_client)
    repository = SQLiteAuditRepository(cfg.audit_db_path) if cfg.audit_db_path else ProposalRepository()
    return TradingSystem(
        config=cfg,
        adapter=adapter,
        execution_gateway=gateway,
        repository=repository,
    )


def _candidate_score(
    proposal: StrategyProposal,
    risk: RiskDecision,
    config: AppConfig,
) -> float:
    score = proposal.regime.confidence
    score += 0.75 if risk.approved else -1.0
    score += 0.10 if proposal.is_live_capable else -0.25
    if risk.risk_budget > 0:
        score -= min(proposal.max_loss / risk.risk_budget, 2.0) * 0.20
    if proposal.regime.entropy > config.max_entropy_for_entry:
        score -= min(proposal.regime.entropy - config.max_entropy_for_entry, 2.0) * 0.10
    return round(score, 4)
