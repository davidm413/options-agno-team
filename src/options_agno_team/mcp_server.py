"""FastMCP tool surface for deterministic system operations."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from options_agno_team.models import to_jsonable
from options_agno_team.service import TradingSystem, build_system


ToolPayload = dict[str, Any] | list[dict[str, Any]] | list[list[dict[str, Any]]]
ToolHandler = Callable[..., ToolPayload]


def build_tool_handlers(system: TradingSystem | None = None) -> dict[str, ToolHandler]:
    app = system or build_system()

    def detect_regime(symbol: str, lookback: int = 120) -> dict[str, Any]:
        return cast(dict[str, Any], to_jsonable(app.detect_regime(symbol, lookback=lookback)))

    def scan_market(symbols: list[str] | None = None, lookback: int = 120) -> list[dict[str, Any]]:
        return cast(list[dict[str, Any]], to_jsonable(app.scan_market(symbols, lookback=lookback)))

    def propose_options_strategy(symbol: str, lookback: int = 120) -> dict[str, Any]:
        return cast(dict[str, Any], to_jsonable(app.propose_options_strategy(symbol, lookback=lookback)))

    def rank_trade_candidates(
        symbols: list[str] | None = None, lookback: int = 120
    ) -> list[dict[str, Any]]:
        return cast(
            list[dict[str, Any]],
            to_jsonable(app.rank_trade_candidates(symbols, lookback=lookback)),
        )

    def check_portfolio_risk(proposal_id: str) -> dict[str, Any]:
        return cast(dict[str, Any], to_jsonable(app.check_portfolio_risk(proposal_id)))

    def live_readiness() -> dict[str, Any]:
        return cast(dict[str, Any], to_jsonable(app.live_readiness()))

    def preflight_strategy(proposal_id: str) -> dict[str, Any]:
        return cast(dict[str, Any], to_jsonable(app.preflight_strategy(proposal_id)))

    def execute_strategy(proposal_id: str) -> dict[str, Any]:
        return cast(dict[str, Any], to_jsonable(app.execute_strategy(proposal_id)))

    def list_paper_positions(open_only: bool = True) -> list[dict[str, Any]]:
        return cast(list[dict[str, Any]], to_jsonable(app.list_paper_positions(open_only=open_only)))

    def mark_to_market() -> list[dict[str, Any]]:
        return cast(list[dict[str, Any]], to_jsonable(app.mark_to_market()))

    def run_backtest(
        symbols: list[str] | None = None,
        lookback: int = 180,
        min_lookback: int = 60,
        holding_period: int = 10,
        step: int = 5,
    ) -> dict[str, Any]:
        return cast(
            dict[str, Any],
            to_jsonable(
                app.run_backtest(
                    symbols,
                    lookback=lookback,
                    min_lookback=min_lookback,
                    holding_period=holding_period,
                    step=step,
                )
            ),
        )

    def monitor_paper_positions() -> list[dict[str, Any]]:
        return cast(list[dict[str, Any]], to_jsonable(app.monitor_paper_positions()))

    def monitor_paper_positions_loop(
        iterations: int = 3,
        interval_seconds: float = 60.0,
    ) -> list[list[dict[str, Any]]]:
        return cast(
            list[list[dict[str, Any]]],
            to_jsonable(
                app.monitor_paper_positions_loop(
                    iterations=iterations,
                    interval_seconds=interval_seconds,
                )
            ),
        )

    def reflect_trades(open_only: bool = True) -> dict[str, Any]:
        return cast(dict[str, Any], to_jsonable(app.reflect_trades(open_only=open_only)))

    return {
        "detect_regime": detect_regime,
        "scan_market": scan_market,
        "propose_options_strategy": propose_options_strategy,
        "rank_trade_candidates": rank_trade_candidates,
        "check_portfolio_risk": check_portfolio_risk,
        "live_readiness": live_readiness,
        "preflight_strategy": preflight_strategy,
        "execute_strategy": execute_strategy,
        "list_paper_positions": list_paper_positions,
        "mark_to_market": mark_to_market,
        "run_backtest": run_backtest,
        "monitor_paper_positions": monitor_paper_positions,
        "monitor_paper_positions_loop": monitor_paper_positions_loop,
        "reflect_trades": reflect_trades,
    }


def create_mcp_app(system: TradingSystem | None = None) -> Any:
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:
        raise RuntimeError("Install the mcp extra to run the FastMCP server") from exc

    mcp = FastMCP("options_regime_trading")
    for name, handler in build_tool_handlers(system).items():
        mcp.tool(name=name)(handler)
    return mcp


if __name__ == "__main__":
    create_mcp_app().run(transport="streamable-http")
