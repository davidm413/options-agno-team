"""Command-line entrypoint for the deterministic trading workflow."""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import replace
from pathlib import Path
from typing import Any, Sequence

from options_agno_team.config import AppConfig
from options_agno_team.models import to_jsonable
from options_agno_team.service import build_system
from options_agno_team.smoke import run_public_smoke


DEFAULT_AUDIT_DB = Path(".options_agno_team") / "audit.sqlite3"


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)

    if args.command == "serve-mcp":
        from options_agno_team.mcp_server import create_mcp_app

        create_mcp_app(_system(args)).run(transport=args.transport)
        return 0

    if args.command == "serve-agent-os":
        from options_agno_team.agno_os import serve_agent_os

        try:
            serve_agent_os(
                system=_system(args),
                model_id=args.model_id,
                ollama_host=args.ollama_host,
                db_file=args.os_db,
                enable_mcp_server=args.enable_mcp,
                host=args.host,
                port=args.port,
                reload=args.reload,
            )
        except RuntimeError as exc:
            parser.exit(status=1, message=f"error: {exc}\n")
        return 0

    if args.command == "public-smoke":
        _print_json(run_public_smoke(args.symbol, config=_config(args)))
        return 0

    system = _system(args)
    if args.command == "detect-regime":
        payload = system.detect_regime(args.symbol, lookback=args.lookback)
    elif args.command == "propose-strategy":
        payload = system.propose_options_strategy(args.symbol, lookback=args.lookback)
    elif args.command == "rank-candidates":
        payload = system.rank_trade_candidates(
            list(args.symbols) if args.symbols else None,
            lookback=args.lookback,
        )
    elif args.command == "check-risk":
        payload = system.check_portfolio_risk(args.proposal_id)
    elif args.command == "live-readiness":
        payload = system.live_readiness()
    elif args.command == "preflight":
        payload = system.preflight_strategy(args.proposal_id)
    elif args.command == "execute":
        payload = system.execute_strategy(args.proposal_id)
    elif args.command == "paper-positions":
        payload = system.list_paper_positions(open_only=not args.all)
    elif args.command == "mark-to-market":
        payload = system.mark_to_market()
    elif args.command == "backtest":
        payload = system.run_backtest(
            list(args.symbols) if args.symbols else None,
            lookback=args.lookback,
            min_lookback=args.min_lookback,
            holding_period=args.holding_period,
            step=args.step,
        )
    elif args.command == "monitor-once":
        payload = system.monitor_paper_positions()
    elif args.command == "monitor-loop":
        payload = system.monitor_paper_positions_loop(
            iterations=args.iterations,
            interval_seconds=args.interval_seconds,
        )
    elif args.command == "reflect-trades":
        payload = system.reflect_trades(open_only=not args.all)
    else:
        parser.error(f"Unhandled command {args.command}")
    _print_json(payload)
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="options-agno")
    parser.add_argument(
        "--db",
        default=os.environ.get("AUDIT_DB_PATH", str(DEFAULT_AUDIT_DB)),
        help="SQLite audit DB path; defaults to AUDIT_DB_PATH or .options_agno_team/audit.sqlite3",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    detect = subparsers.add_parser("detect-regime", help="Detect the current market regime")
    detect.add_argument("symbol")
    detect.add_argument("--lookback", type=int, default=120)

    propose = subparsers.add_parser("propose-strategy", help="Create and persist a strategy proposal")
    propose.add_argument("symbol")
    propose.add_argument("--lookback", type=int, default=120)

    rank = subparsers.add_parser(
        "rank-candidates",
        help="Rank strategy candidates using deterministic proposal and risk tools",
    )
    rank.add_argument("symbols", nargs="*", help="Symbols to rank; defaults to configured universe")
    rank.add_argument("--lookback", type=int, default=120)

    risk = subparsers.add_parser("check-risk", help="Run deterministic risk checks for a proposal")
    risk.add_argument("proposal_id")

    subparsers.add_parser("live-readiness", help="Show live trading readiness gates")

    preflight = subparsers.add_parser("preflight", help="Run dry-run or live Public preflight")
    preflight.add_argument("proposal_id")

    execute = subparsers.add_parser("execute", help="Execute through the gated dry-run/live path")
    execute.add_argument("proposal_id")

    positions = subparsers.add_parser("paper-positions", help="List simulated paper positions")
    positions.add_argument("--all", action="store_true", help="Include closed positions")

    subparsers.add_parser("mark-to-market", help="Refresh paper position marks and P&L")

    backtest = subparsers.add_parser("backtest", help="Replay historical bars through the pipeline")
    backtest.add_argument("symbols", nargs="*", help="Symbols to test; defaults to configured universe")
    backtest.add_argument("--lookback", type=int, default=180)
    backtest.add_argument("--min-lookback", type=int, default=60)
    backtest.add_argument("--holding-period", type=int, default=10)
    backtest.add_argument("--step", type=int, default=5)

    subparsers.add_parser("monitor-once", help="Refresh paper positions and detect exit triggers")

    monitor_loop = subparsers.add_parser("monitor-loop", help="Run repeated paper-position monitoring")
    monitor_loop.add_argument("--iterations", type=int, default=3)
    monitor_loop.add_argument("--interval-seconds", type=float, default=60.0)

    reflections = subparsers.add_parser("reflect-trades", help="Build learning reflections for paper trades")
    reflections.add_argument("--all", action="store_true", help="Include closed positions")

    smoke = subparsers.add_parser("public-smoke", help="Run env-gated live Public.com smoke checks")
    smoke.add_argument("symbol")

    serve = subparsers.add_parser("serve-mcp", help="Start the FastMCP server")
    serve.add_argument("--transport", default="streamable-http")

    agent_os = subparsers.add_parser("serve-agent-os", help="Start the Agno AgentOS server")
    agent_os.add_argument("--model-id", default=os.environ.get("AGNO_MODEL_ID"))
    agent_os.add_argument("--ollama-host", default=os.environ.get("AGNO_OLLAMA_HOST"))
    agent_os.add_argument(
        "--os-db",
        default=os.environ.get("AGNO_OS_DB_PATH", ".options_agno_team/agno_os.sqlite3"),
        help="AgentOS SQLite DB path; defaults to AGNO_OS_DB_PATH or .options_agno_team/agno_os.sqlite3",
    )
    agent_os.add_argument("--host", default="localhost")
    agent_os.add_argument("--port", type=int, default=7777)
    agent_os.add_argument("--reload", action="store_true")
    agent_os.add_argument("--enable-mcp", action="store_true", help="Enable AgentOS MCP endpoint")
    return parser


def _config(args: argparse.Namespace) -> AppConfig:
    config = AppConfig.from_env()
    db_path = Path(args.db)
    return replace(config, audit_db_path=str(db_path))


def _system(args: argparse.Namespace) -> Any:
    return build_system(_config(args))


def _print_json(payload: Any) -> None:
    print(json.dumps(to_jsonable(payload), indent=2, sort_keys=True))


if __name__ == "__main__":
    raise SystemExit(main())
