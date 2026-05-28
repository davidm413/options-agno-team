"""FastMCP tool surface for deterministic system operations."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from options_agno_team.models import to_jsonable
from options_agno_team.service import TradingSystem, build_system


ToolHandler = Callable[..., dict[str, Any] | list[dict[str, Any]]]


def build_tool_handlers(system: TradingSystem | None = None) -> dict[str, ToolHandler]:
    app = system or build_system()

    def detect_regime(symbol: str, lookback: int = 120) -> dict[str, Any]:
        return to_jsonable(app.detect_regime(symbol, lookback=lookback))

    def scan_market(symbols: list[str] | None = None, lookback: int = 120) -> list[dict[str, Any]]:
        return to_jsonable(app.scan_market(symbols, lookback=lookback))

    def propose_options_strategy(symbol: str, lookback: int = 120) -> dict[str, Any]:
        return to_jsonable(app.propose_options_strategy(symbol, lookback=lookback))

    def check_portfolio_risk(proposal_id: str) -> dict[str, Any]:
        return to_jsonable(app.check_portfolio_risk(proposal_id))

    def preflight_strategy(proposal_id: str) -> dict[str, Any]:
        return to_jsonable(app.preflight_strategy(proposal_id))

    def execute_strategy(proposal_id: str) -> dict[str, Any]:
        return to_jsonable(app.execute_strategy(proposal_id))

    return {
        "detect_regime": detect_regime,
        "scan_market": scan_market,
        "propose_options_strategy": propose_options_strategy,
        "check_portfolio_risk": check_portfolio_risk,
        "preflight_strategy": preflight_strategy,
        "execute_strategy": execute_strategy,
    }


def create_mcp_app(system: TradingSystem | None = None) -> Any:
    try:
        from mcp.server.fastmcp import FastMCP  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError("Install the mcp extra to run the FastMCP server") from exc

    mcp = FastMCP("options_regime_trading")
    for name, handler in build_tool_handlers(system).items():
        mcp.tool(name=name)(handler)
    return mcp


if __name__ == "__main__":
    create_mcp_app().run(transport="streamable-http")
