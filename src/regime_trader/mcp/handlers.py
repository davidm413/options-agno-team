from __future__ import annotations

from uuid import uuid4

from regime_trader.config.models import AppConfig
from regime_trader.data.interfaces import BrokerExecutionProvider, MarketDataProvider
from regime_trader.learning.reflection import reflect_on_trade
from regime_trader.mcp.auth import AuthorizationContext
from regime_trader.mcp.schemas import (
    CheckPortfolioRiskInput,
    CompareRegimesInput,
    DetectRegimeInput,
    DetectRegimeOutput,
    ExecuteTradeInput,
    ExecuteTradeOutput,
    ProposeOptionsStrategyInput,
    ScanMarketInput,
    ToolError,
)
from regime_trader.mcp.server import TradingToolService
from regime_trader.persistence.live_state import LiveStateRepository
from regime_trader.regimes.service import RegimeService
from regime_trader.scanner.service import MarketScanner, MarketScanResult
from regime_trader.schemas.learning import ReflectionResult, TradeJournalEntry
from regime_trader.schemas.regime import RegimeOutput
from regime_trader.schemas.trading import ExecutionRequest, RiskDecision, StrategyProposal
from regime_trader.trading.execution import ExecutionEngine
from regime_trader.trading.risk import RiskEngine
from regime_trader.trading.strategy import StrategyEngine


class McpToolHandlers:
    def __init__(
        self,
        *,
        config: AppConfig,
        provider: MarketDataProvider,
        execution_provider: BrokerExecutionProvider | None = None,
        guard: TradingToolService | None = None,
        live_state: LiveStateRepository | None = None,
    ) -> None:
        self.config = config
        self.provider = provider
        self.guard = guard or TradingToolService()
        self.live_state = live_state or LiveStateRepository(ttl_seconds=config.persistence.live_state_ttl_seconds)
        self.regimes = RegimeService(config.features, config.regimes)
        self.scanner = MarketScanner(config, provider, self.regimes)
        self.strategies = StrategyEngine(config.strategies)
        self.risk = RiskEngine(config.risk)
        self.execution = ExecutionEngine(config.execution, execution_provider)

    def detect_regime(self, payload: DetectRegimeInput, context: AuthorizationContext) -> DetectRegimeOutput:
        try:
            self.guard.validate_authorized("detect_regime", context, payload.model_dump(mode="json"))
            bars = tuple(
                self.provider.get_bars(
                    payload.symbol,
                    interval="1d",
                    limit=payload.lookback_bars or self.config.features.lookback_bars,
                )
            )
            chain = self.provider.get_option_chain(payload.symbol) if payload.include_options else None
            return DetectRegimeOutput(regime=self.regimes.detect(payload.symbol, bars, option_chain=chain))
        except Exception as exc:
            return DetectRegimeOutput(error=ToolError(code="detect_regime_failed", message=str(exc)))

    def compare_regimes(self, payload: CompareRegimesInput, context: AuthorizationContext) -> tuple[RegimeOutput, ...]:
        self.guard.validate_authorized("compare_regimes", context, payload.model_dump(mode="json"))
        outputs: list[RegimeOutput] = []
        for symbol in payload.symbols:
            result = self.detect_regime(DetectRegimeInput(symbol=symbol), context)
            if result.regime is not None:
                outputs.append(result.regime)
        return tuple(outputs)

    def scan_market(self, payload: ScanMarketInput, context: AuthorizationContext) -> MarketScanResult:
        self.guard.validate_authorized("scan_market", context, payload.model_dump(mode="json"))
        return self.scanner.scan(symbols=payload.symbols, asset_class=payload.asset_class)

    def propose_options_strategy(
        self, payload: ProposeOptionsStrategyInput, context: AuthorizationContext
    ) -> StrategyProposal:
        self.guard.validate_authorized("propose_options_strategy", context, payload.model_dump(mode="json"))
        regime_output = self.detect_regime(DetectRegimeInput(symbol=payload.symbol, include_options=True), context)
        if regime_output.regime is None:
            raise ValueError(regime_output.error.message if regime_output.error else "regime unavailable")
        chain = self.provider.get_option_chain(payload.symbol, expiration=payload.expiration)
        return self.strategies.propose(regime_output.regime, chain, config_version=self.config.version)

    def check_portfolio_risk(self, payload: CheckPortfolioRiskInput, context: AuthorizationContext) -> RiskDecision:
        self.guard.validate_authorized("check_portfolio_risk", context, payload.model_dump(mode="json"))
        accounts = tuple(self.provider.get_accounts())
        if not accounts:
            raise ValueError("account_unavailable")
        positions = tuple(self.provider.get_positions(payload.account_id))
        return self.risk.review(payload.proposal, account=accounts[0], positions=positions)

    def execute_trade(self, payload: ExecuteTradeInput, context: AuthorizationContext) -> ExecuteTradeOutput:
        try:
            self.guard.validate_authorized("execute_trade", context, payload.model_dump(mode="json"))
            preflight = self.execution.run_preflight(payload.proposal) if payload.mode == "live" else None
            request = ExecutionRequest(
                request_id=f"mcp-{uuid4().hex}",
                proposal=payload.proposal,
                risk_decision=payload.risk_decision,
                preflight=preflight,
                mode=payload.mode,
                operator_approved=payload.operator_approved,
                idempotency_key=payload.idempotency_key,
            )
            return ExecuteTradeOutput(execution=self.execution.execute(request))
        except Exception as exc:
            return ExecuteTradeOutput(error=ToolError(code="execute_trade_failed", message=str(exc)))

    def get_live_monitoring(self, symbol: str, context: AuthorizationContext) -> dict[str, object]:
        self.guard.validate_authorized("get_live_monitoring", context, {"symbol": symbol})
        record = self.live_state.get(f"monitoring:{symbol.upper()}")
        if record is None:
            return {"symbol": symbol.upper(), "status": "missing"}
        return {"symbol": symbol.upper(), "status": "stale" if record.stale else "current", "payload": record.payload}

    def reflect_on_trade(self, entry: TradeJournalEntry, context: AuthorizationContext) -> ReflectionResult:
        self.guard.validate_authorized("reflect_on_trade", context, {"journal_id": entry.journal_id})
        return reflect_on_trade(entry)
