"""AgentOS runtime wiring for the options trading team."""

from __future__ import annotations

import json
import os
from collections.abc import Callable, Sequence
from importlib import import_module
from pathlib import Path
from typing import Any

from options_agno_team.agents import build_agno_agents, build_agno_team
from options_agno_team.models import to_jsonable
from options_agno_team.service import TradingSystem, build_system


DEFAULT_AGNO_MODEL_ID = "llama3.1:8b"
DEFAULT_AGNO_OS_DB = Path(".options_agno_team") / "agno_os.sqlite3"
DEFAULT_AGENT_OS_HOST = "localhost"
DEFAULT_AGENT_OS_PORT = 7777


def build_trading_tool_functions(system: TradingSystem | None = None) -> tuple[Callable[..., str], ...]:
    app = system or build_system()

    def detect_regime(symbol: str, lookback: int = 120) -> str:
        """Detect the current market regime for one symbol using deterministic market data."""
        return _json(app.detect_regime(symbol, lookback=lookback))

    def scan_market(symbols: list[str] | None = None, lookback: int = 120) -> str:
        """Rank configured or supplied symbols by deterministic regime confidence."""
        return _json(app.scan_market(symbols, lookback=lookback))

    def propose_options_strategy(symbol: str, lookback: int = 120) -> str:
        """Create and persist a deterministic options strategy proposal for one symbol."""
        return _json(app.propose_options_strategy(symbol, lookback=lookback))

    def rank_trade_candidates(
        symbols: list[str] | None = None,
        lookback: int = 120,
    ) -> str:
        """Rank symbols using deterministic proposal, risk, and candidate scoring tools."""
        return _json(app.rank_trade_candidates(symbols, lookback=lookback))

    def check_portfolio_risk(proposal_id: str) -> str:
        """Approve or reject a persisted proposal using deterministic portfolio risk checks."""
        return _json(app.check_portfolio_risk(proposal_id))

    def live_readiness() -> str:
        """Report every live-trading readiness gate and blocker."""
        return _json(app.live_readiness())

    def preflight_strategy(proposal_id: str) -> str:
        """Run dry-run or live broker preflight for an approved proposal without placement."""
        return _json(app.preflight_strategy(proposal_id))

    def execute_strategy(proposal_id: str) -> str:
        """Execute a proposal through the gated dry-run/live execution path."""
        return _json(app.execute_strategy(proposal_id))

    def list_paper_positions(open_only: bool = True) -> str:
        """List current paper-trading positions persisted by the audit repository."""
        return _json(app.list_paper_positions(open_only=open_only))

    def mark_to_market() -> str:
        """Refresh spread marks and unrealized P&L for current paper positions."""
        return _json(app.mark_to_market())

    def run_backtest(
        symbols: list[str] | None = None,
        lookback: int = 180,
        min_lookback: int = 60,
        holding_period: int = 10,
        step: int = 5,
    ) -> str:
        """Replay historical fixture or Public data through regime, strategy, and risk logic."""
        return _json(
            app.run_backtest(
                symbols,
                lookback=lookback,
                min_lookback=min_lookback,
                holding_period=holding_period,
                step=step,
            )
        )

    def monitor_paper_positions() -> str:
        """Refresh open paper positions and return exit-review monitoring events."""
        return _json(app.monitor_paper_positions())

    def reflect_trades(open_only: bool = True) -> str:
        """Summarize paper-trade outcomes against their original market thesis."""
        return _json(app.reflect_trades(open_only=open_only))

    return (
        detect_regime,
        scan_market,
        propose_options_strategy,
        rank_trade_candidates,
        check_portfolio_risk,
        live_readiness,
        preflight_strategy,
        execute_strategy,
        list_paper_positions,
        mark_to_market,
        run_backtest,
        monitor_paper_positions,
        reflect_trades,
    )


def build_open_source_model(
    *,
    model_id: str | None = None,
    host: str | None = None,
) -> Any:
    try:
        Ollama = getattr(import_module("agno.models.ollama"), "Ollama")
    except ImportError as exc:
        raise RuntimeError(
            'Install the agno extra to use the open-source Ollama model: '
            'python -m pip install -e ".[agno]"'
        ) from exc

    selected_model_id = model_id or os.environ.get("AGNO_MODEL_ID") or DEFAULT_AGNO_MODEL_ID
    selected_host = host or os.environ.get("AGNO_OLLAMA_HOST") or os.environ.get("OLLAMA_HOST")
    if selected_host:
        return Ollama(id=selected_model_id, host=selected_host)
    return Ollama(id=selected_model_id)


def create_agent_os(
    *,
    system: TradingSystem | None = None,
    model: Any | None = None,
    model_id: str | None = None,
    ollama_host: str | None = None,
    db_file: str | Path | None = None,
    enable_mcp_server: bool = False,
) -> Any:
    try:
        SqliteDb = getattr(import_module("agno.db.sqlite"), "SqliteDb")
        AgentOS = getattr(import_module("agno.os"), "AgentOS")
    except ImportError as exc:
        raise RuntimeError(
            'Install the agno extra to run AgentOS: python -m pip install -e ".[agno]"'
        ) from exc

    db_path = _resolve_db_file(db_file)
    db = SqliteDb(db_file=str(db_path), id="options-agno-os-db")
    selected_model = model or build_open_source_model(model_id=model_id, host=ollama_host)
    tools = build_trading_tool_functions(system)
    agents = build_agno_agents(tools=tools, model=selected_model, db=db)
    team = build_agno_team(members=agents, model=selected_model, db=db)
    return AgentOS(
        id="options-agno-team",
        name="Options Agno Team",
        description="AgentOS runtime for deterministic market regime and options workflows.",
        agents=agents,
        teams=[team],
        db=db,
        enable_mcp_server=enable_mcp_server,
    )


def create_agent_os_app(
    *,
    system: TradingSystem | None = None,
    model: Any | None = None,
    model_id: str | None = None,
    ollama_host: str | None = None,
    db_file: str | Path | None = None,
    enable_mcp_server: bool = False,
) -> Any:
    return create_agent_os(
        system=system,
        model=model,
        model_id=model_id,
        ollama_host=ollama_host,
        db_file=db_file,
        enable_mcp_server=enable_mcp_server,
    ).get_app()


def serve_agent_os(
    *,
    system: TradingSystem | None = None,
    model_id: str | None = None,
    ollama_host: str | None = None,
    db_file: str | Path | None = None,
    enable_mcp_server: bool = False,
    host: str = DEFAULT_AGENT_OS_HOST,
    port: int = DEFAULT_AGENT_OS_PORT,
    reload: bool = False,
) -> None:
    agent_os = create_agent_os(
        system=system,
        model_id=model_id,
        ollama_host=ollama_host,
        db_file=db_file,
        enable_mcp_server=enable_mcp_server,
    )
    app = agent_os.get_app()
    agent_os.serve(app=app, host=host, port=port, reload=reload)


def _resolve_db_file(db_file: str | Path | None) -> Path:
    configured = db_file or os.environ.get("AGNO_OS_DB_PATH") or DEFAULT_AGNO_OS_DB
    path = Path(configured)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _json(payload: Any) -> str:
    return json.dumps(to_jsonable(payload), indent=2, sort_keys=True)


def tool_names(tools: Sequence[Callable[..., str]]) -> tuple[str, ...]:
    return tuple(tool.__name__ for tool in tools)
