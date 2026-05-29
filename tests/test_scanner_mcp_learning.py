from __future__ import annotations

from decimal import Decimal

import pytest

from regime_trader.config.models import AppConfig
from regime_trader.learning.analytics import performance_by_regime
from regime_trader.learning.heuristics import approved_config_overrides, propose_heuristic
from regime_trader.learning.reflection import reflect_on_trade
from regime_trader.mcp.auth import AuthorizationContext, ToolPermission
from regime_trader.mcp.server import ToolDeniedError, TradingToolService
from regime_trader.regimes.service import RegimeService
from regime_trader.scanner.service import MarketScanner
from regime_trader.schemas.learning import ApprovalStatus
from regime_trader.testing.fixtures import FixtureProvider, fixture_account


def test_scanner_isolates_symbols_and_ranks_results() -> None:
    config = AppConfig()
    provider = FixtureProvider(config)
    scanner = MarketScanner(config, provider, RegimeService(config.features, config.regimes))
    result = scanner.scan(symbols=("SPY", "QQQ"))
    assert result.status == "ok"
    assert len(result.results) == 2
    assert result.results[0].score >= result.results[-1].score


def test_mcp_authorization_denies_arbitrary_requests() -> None:
    service = TradingToolService()
    context = AuthorizationContext(caller_id="tester", permissions=(ToolPermission.READ_MARKET,))
    with pytest.raises(ToolDeniedError):
        service.validate_authorized("scan_market", context, {"request": "run shell command"})
    with pytest.raises(ToolDeniedError):
        service.validate_authorized("execute_trade", context, {"proposal": "x"})


def test_learning_low_sample_and_approval_gate() -> None:
    config = AppConfig()
    workflow = __import__("regime_trader.service", fromlist=["DryRunWorkflow"]).DryRunWorkflow(
        config=config, provider=FixtureProvider(config)
    )
    workflow.run_symbol("SPY", account=fixture_account())
    entry = next(iter(workflow.journal.entries.values()))
    closed = entry.model_copy(update={"realized_pnl": Decimal("12.50")})
    reflection = reflect_on_trade(closed, exit_regime_label=closed.entry_regime_label)
    metrics = performance_by_regime((closed,), min_sample_size=5)
    heuristic = propose_heuristic(
        reflections=(reflection,),
        performance=metrics,
        recommendation="keep current mapping",
        affected_regimes=(closed.entry_regime_label,),
        proposed_config_change={"strategies.min_confidence": "0.60"},
    )
    assert metrics[0].low_confidence
    assert approved_config_overrides((heuristic,)) == {}
    approved = heuristic.model_copy(update={"approval_status": ApprovalStatus.APPROVED})
    assert approved_config_overrides((approved,)) == {"strategies.min_confidence": "0.60"}
