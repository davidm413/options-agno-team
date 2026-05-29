"""Agno agent/team wiring kept separate from deterministic services."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AgentRoleSpec:
    name: str
    role: str
    instructions: tuple[str, ...]


def build_agent_specs() -> tuple[AgentRoleSpec, ...]:
    return (
        AgentRoleSpec(
            name="Regime Detection Agent",
            role="Runs deterministic regime tools and explains drivers.",
            instructions=("Use detect_regime and scan_market only for market regime facts.",),
        ),
        AgentRoleSpec(
            name="Options Strategy Agent",
            role="Turns approved regime snapshots into options strategy proposals.",
            instructions=(
                "Use propose_options_strategy; do not invent contracts, greeks, prices, or liquidity.",
            ),
        ),
        AgentRoleSpec(
            name="Trade Ranking Agent",
            role="Ranks proposed candidates using deterministic scores and risk decisions.",
            instructions=(
                "Use rank_trade_candidates for ranking; do not create scores manually.",
                "Explain ranking with returned rationale, regime, risk status, and score only.",
            ),
        ),
        AgentRoleSpec(
            name="Risk Agent",
            role="Approves or rejects proposals using deterministic risk tools.",
            instructions=("Use check_portfolio_risk before any preflight or execution.",),
        ),
        AgentRoleSpec(
            name="Execution Agent",
            role="Handles preflight and gated execution.",
            instructions=(
                "Use check_portfolio_risk and preflight_strategy before execute_strategy.",
                "Never place or simulate an execution for a rejected risk decision.",
            ),
        ),
        AgentRoleSpec(
            name="Monitoring Agent",
            role="Monitors open positions and regime changes.",
            instructions=(
                "Use list_paper_positions, mark_to_market, and monitor_paper_positions for paper position state.",
                "Report risk changes; do not place trades directly.",
            ),
        ),
        AgentRoleSpec(
            name="Learning Reflection Agent",
            role="Summarizes post-trade outcomes for future parameter review.",
            instructions=(
                "Use reflect_trades and run_backtest to compare outcomes against the original thesis.",
                "Record observations; do not modify execution gates.",
            ),
        ),
    )


def build_agno_agents(
    *,
    tools: Sequence[Any],
    model: Any | None = None,
    db: Any | None = None,
) -> list[Any]:
    try:
        from agno.agent import Agent  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError("Install the agno extra to build Agno agents") from exc

    members = []
    for spec in build_agent_specs():
        kwargs: dict[str, Any] = {}
        if db is not None:
            kwargs["db"] = db
        members.append(
            Agent(
                id=_agent_id(spec.name),
                name=spec.name,
                role=spec.role,
                model=model,
                tools=list(tools),
                instructions=list(spec.instructions),
                markdown=True,
                **kwargs,
            )
        )
    return members


def build_agno_team(
    *,
    mcp_tools: Any | None = None,
    tools: Sequence[Any] | None = None,
    members: Sequence[Any] | None = None,
    model: Any | None = None,
    db: Any | None = None,
) -> Any:
    try:
        from agno.team import Team  # type: ignore[import-not-found]
        from agno.team.mode import TeamMode  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError("Install the agno extra to build the Agno team") from exc

    if members is None and tools is None and mcp_tools is None:
        raise ValueError("Provide mcp_tools, tools, or members to build the Agno team")

    agno_tools = list(tools) if tools is not None else [mcp_tools]
    team_members = list(members) if members is not None else build_agno_agents(
        tools=agno_tools,
        model=model,
        db=db,
    )
    kwargs: dict[str, Any] = {}
    if db is not None:
        kwargs["db"] = db
    return Team(
        id="options-trading-team",
        name="Regime Options Trading Team",
        mode=TeamMode.coordinate,
        model=model,
        members=team_members,
        instructions=[
            "Coordinate specialist agents using only deterministic trading tools.",
            "All math, prices, greeks, scores, and risk status must come from tool output.",
            "Never bypass risk approval, preflight, or live execution gates.",
        ],
        show_members_responses=True,
        markdown=True,
        **kwargs,
    )


def _agent_id(name: str) -> str:
    return name.lower().replace(" ", "-")
