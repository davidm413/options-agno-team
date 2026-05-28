"""Gated dry-run and live execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from options_agno_team.config import AppConfig, ExecutionMode
from options_agno_team.models import (
    ExecutionResult,
    ExecutionStatus,
    OrderIntent,
    OrderSide,
    RiskDecision,
    StrategyProposal,
    StrategyType,
    to_jsonable,
)


@dataclass
class ProposalRepository:
    proposals: dict[str, StrategyProposal] = field(default_factory=dict)
    risk_decisions: dict[str, RiskDecision] = field(default_factory=dict)

    def save_proposal(self, proposal: StrategyProposal) -> None:
        self.proposals[proposal.proposal_id] = proposal

    def save_risk_decision(self, decision: RiskDecision) -> None:
        self.risk_decisions[decision.proposal_id] = decision

    def get_proposal(self, proposal_id: str) -> StrategyProposal:
        return self.proposals[proposal_id]

    def get_risk_decision(self, proposal_id: str) -> RiskDecision:
        return self.risk_decisions[proposal_id]


class ExecutionGateway:
    def __init__(self, *, config: AppConfig | None = None, public_client: Any | None = None) -> None:
        self.config = config or AppConfig()
        self.public_client = public_client
        self.audit_log: list[str] = []

    def preflight(self, proposal: StrategyProposal, risk: RiskDecision) -> ExecutionResult:
        intent = _order_intent(proposal)
        if self.config.execution_mode is ExecutionMode.DRY_RUN:
            message = "dry-run preflight recorded; no broker call made"
            return self._result(proposal, ExecutionStatus.DRY_RUN, message, intent, None)
        rejection = self._live_rejection(proposal, risk)
        if rejection:
            return self._result(proposal, ExecutionStatus.REJECTED, rejection, intent, None)
        preflight_response = self._call_public_preflight(proposal, intent)
        return self._result(
            proposal,
            ExecutionStatus.PREFLIGHTED,
            "live preflight succeeded",
            intent,
            _response_to_dict(preflight_response),
        )

    def execute(self, proposal: StrategyProposal, risk: RiskDecision) -> ExecutionResult:
        intent = _order_intent(proposal)
        if self.config.execution_mode is ExecutionMode.DRY_RUN:
            return self._result(
                proposal,
                ExecutionStatus.DRY_RUN,
                "dry-run order recorded; no live order submitted",
                intent,
                None,
            )
        rejection = self._live_rejection(proposal, risk)
        if rejection:
            return self._result(proposal, ExecutionStatus.REJECTED, rejection, intent, None)
        preflight_response = self._call_public_preflight(proposal, intent)
        order = self._call_public_place(proposal, intent)
        order_id = getattr(order, "order_id", None)
        return self._result(
            proposal,
            ExecutionStatus.PLACED,
            "live order submitted after preflight",
            intent,
            _response_to_dict(preflight_response),
            order_id=order_id,
        )

    def _live_rejection(self, proposal: StrategyProposal, risk: RiskDecision) -> str | None:
        if not self.config.live_order_enabled:
            return "live trading disabled by config"
        if self.public_client is None:
            return "public client is required for live execution"
        if not risk.approved:
            return "risk decision is not approved"
        if not proposal.is_live_capable:
            return f"{proposal.strategy_type.value} is not live-capable"
        if proposal.strategy_type.value not in self.config.allowed_live_strategies:
            return f"{proposal.strategy_type.value} is not allowed for live execution"
        return None

    def _call_public_preflight(self, proposal: StrategyProposal, intent: OrderIntent) -> Any:
        method_name = _public_method_name(proposal.strategy_type, prefix="preflight")
        method = getattr(self.public_client, method_name)
        kwargs = _spread_kwargs(proposal, intent)
        return method(**kwargs)

    def _call_public_place(self, proposal: StrategyProposal, intent: OrderIntent) -> Any:
        method_name = _public_method_name(proposal.strategy_type, prefix="place")
        method = getattr(self.public_client, method_name)
        kwargs = _spread_kwargs(proposal, intent)
        return method(**kwargs)

    def _result(
        self,
        proposal: StrategyProposal,
        status: ExecutionStatus,
        message: str,
        intent: OrderIntent | None,
        preflight: dict[str, Any] | None,
        *,
        order_id: str | None = None,
    ) -> ExecutionResult:
        entry = f"{proposal.proposal_id}:{status.value}:{message}"
        self.audit_log.append(entry)
        return ExecutionResult(
            proposal_id=proposal.proposal_id,
            status=status,
            message=message,
            order_intent=intent,
            preflight=preflight,
            order_id=order_id,
            audit=tuple(self.audit_log),
        )


def _order_intent(proposal: StrategyProposal) -> OrderIntent:
    limit_price = proposal.estimated_debit if proposal.estimated_debit is not None else proposal.estimated_credit
    return OrderIntent(
        proposal_id=proposal.proposal_id,
        strategy_type=proposal.strategy_type,
        symbol=proposal.symbol,
        quantity=proposal.quantity,
        legs=proposal.legs,
        limit_price=round(float(limit_price or 0.01), 2),
    )


def _public_method_name(strategy: StrategyType, *, prefix: str) -> str:
    mapping = {
        StrategyType.BULL_CALL_DEBIT_SPREAD: "call_debit_spread",
        StrategyType.BEAR_PUT_DEBIT_SPREAD: "put_debit_spread",
        StrategyType.BULL_PUT_CREDIT_SPREAD: "put_credit_spread",
        StrategyType.BEAR_CALL_CREDIT_SPREAD: "call_credit_spread",
    }
    if strategy not in mapping:
        raise ValueError(f"{strategy.value} is not supported by Public spread helpers")
    return f"{prefix}_{mapping[strategy]}"


def _spread_kwargs(proposal: StrategyProposal, intent: OrderIntent) -> dict[str, Any]:
    if proposal.strategy_type in {
        StrategyType.BULL_CALL_DEBIT_SPREAD,
        StrategyType.BEAR_PUT_DEBIT_SPREAD,
    }:
        buy_leg = next(leg for leg in proposal.legs if leg.side is OrderSide.BUY)
        sell_leg = next(leg for leg in proposal.legs if leg.side is OrderSide.SELL)
    else:
        sell_leg = next(leg for leg in proposal.legs if leg.side is OrderSide.SELL)
        buy_leg = next(leg for leg in proposal.legs if leg.side is OrderSide.BUY)
    return {
        "sell_contract_osi": sell_leg.contract_symbol,
        "buy_contract_osi": buy_leg.contract_symbol,
        "quantity": proposal.quantity,
        "limit_price": intent.limit_price,
    }


def _response_to_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if hasattr(value, "model_dump"):
        return to_jsonable(value.model_dump())
    if hasattr(value, "__dict__"):
        return to_jsonable(vars(value))
    if isinstance(value, dict):
        return to_jsonable(value)
    return {"value": str(value)}
