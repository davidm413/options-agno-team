"""Env-gated live Public.com smoke checks."""

from __future__ import annotations

import os
from typing import Any, Mapping

from options_agno_team.config import AppConfig, DataMode, ExecutionMode
from options_agno_team.models import to_jsonable
from options_agno_team.readiness import evaluate_live_readiness
from options_agno_team.service import build_system


PUBLIC_SMOKE_ENV = "PUBLIC_SMOKE_ENABLED"


def run_public_smoke(
    symbol: str,
    *,
    config: AppConfig | None = None,
    public_client: Any | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    values = env if env is not None else os.environ
    if not _enabled(values.get(PUBLIC_SMOKE_ENV)):
        raise RuntimeError(f"Set {PUBLIC_SMOKE_ENV}=true to run live Public.com smoke checks")

    cfg = config or AppConfig.from_env(values)
    if cfg.data_mode is not DataMode.PUBLIC:
        raise RuntimeError("Set DATA_MODE=public to run Public.com smoke checks")
    if cfg.execution_mode is ExecutionMode.LIVE:
        readiness = evaluate_live_readiness(cfg)
        if not readiness.ready:
            raise RuntimeError("Live readiness failed: " + "; ".join(readiness.blockers))

    system = build_system(cfg, public_client=public_client)
    adapter = system.adapter
    symbol = symbol.upper()

    bars = adapter.get_bars(symbol, lookback=30)
    quotes = adapter.get_quotes([symbol])
    expirations = adapter.get_option_expirations(symbol)
    chain = adapter.get_option_chain(symbol, expiration_date=expirations[0])
    greeks = adapter.get_option_greeks([contract.symbol for contract in chain[:4]])
    account = adapter.get_account()
    positions = adapter.get_positions()

    proposal = system.propose_options_strategy(symbol, lookback=30)
    risk = system.check_portfolio_risk(proposal.proposal_id)
    preflight = system.preflight_strategy(proposal.proposal_id)

    return {
        "symbol": symbol,
        "bars": len(bars),
        "quotes": sorted(quotes),
        "expirations": expirations,
        "option_contracts": len(chain),
        "greeks_checked": len(greeks),
        "account": account,
        "positions": positions,
        "proposal": to_jsonable(proposal),
        "risk": to_jsonable(risk),
        "preflight": to_jsonable(preflight),
    }


def _enabled(value: str | None) -> bool:
    return value is not None and value.strip().lower() in {"1", "true", "yes", "y", "on"}
