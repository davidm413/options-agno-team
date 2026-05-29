from __future__ import annotations

from regime_trader.config.models import AppConfig
from regime_trader.mcp.auth import AuthorizationContext, ToolPermission
from regime_trader.mcp.handlers import McpToolHandlers
from regime_trader.mcp.schemas import DetectRegimeInput, ScanMarketInput
from regime_trader.testing.fixtures import FixtureProvider


def test_mcp_handlers_call_deterministic_services() -> None:
    config = AppConfig()
    context = AuthorizationContext(
        caller_id="tester",
        permissions=(ToolPermission.READ_MARKET,),
    )
    handlers = McpToolHandlers(config=config, provider=FixtureProvider(config))
    detected = handlers.detect_regime(DetectRegimeInput(symbol="SPY"), context)
    assert detected.regime is not None
    scan = handlers.scan_market(ScanMarketInput(symbols=("SPY",)), context)
    assert scan.status == "ok"
