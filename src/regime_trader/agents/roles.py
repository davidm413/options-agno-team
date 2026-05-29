from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AgentRole:
    name: str
    responsibility: str
    input_contracts: tuple[str, ...]
    output_contract: str


AGENT_ROLES: tuple[AgentRole, ...] = (
    AgentRole(
        "regime_detection",
        "Call deterministic regime services",
        ("DetectRegimeInput",),
        "RegimeOutput",
    ),
    AgentRole(
        "options_strategy",
        "Map regimes to bounded strategy proposals",
        ("RegimeOutput",),
        "StrategyProposal",
    ),
    AgentRole(
        "risk_portfolio",
        "Evaluate buying power, Greeks, concentration, and limits",
        ("StrategyProposal",),
        "RiskDecision",
    ),
    AgentRole(
        "execution",
        "Run preflight and gated dry-run/live execution",
        ("RiskDecision", "PreflightResult"),
        "ExecutionRecord",
    ),
    AgentRole(
        "monitoring",
        "Watch positions against regime, P&L, Greeks, and expiration",
        ("Position", "RegimeOutput"),
        "MonitoringSnapshot",
    ),
    AgentRole(
        "learning",
        "Reflect on closed trades and propose approved heuristics",
        ("TradeJournalEntry",),
        "ReflectionResult",
    ),
)


def build_agno_agents(roles: Sequence[AgentRole] = AGENT_ROLES) -> list[Any]:
    try:
        from agno.agent import Agent
    except Exception:  # pragma: no cover - optional runtime import
        return list(roles)
    return [
        Agent(
            name=role.name,
            instructions=[
                role.responsibility,
                "Use typed service outputs only. Do not infer regime, risk, or execution state.",
                "Never request shell, Python, SQL, unrestricted HTTP, or raw credentials.",
            ],
        )
        for role in roles
    ]
