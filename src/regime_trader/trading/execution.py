from __future__ import annotations

from uuid import uuid4

from regime_trader.config.models import ExecutionConfig
from regime_trader.data.interfaces import BrokerExecutionProvider
from regime_trader.schemas.trading import (
    DecisionStatus,
    ExecutionMode,
    ExecutionRecord,
    ExecutionRequest,
    PreflightResult,
    StrategyProposal,
)


class ExecutionEngine:
    def __init__(self, config: ExecutionConfig, provider: BrokerExecutionProvider | None = None) -> None:
        self.config = config
        self.provider = provider

    def run_preflight(self, proposal: StrategyProposal) -> PreflightResult:
        if self.provider is None:
            return PreflightResult(
                preflight_id=f"preflight-{uuid4().hex}",
                proposal_id=proposal.proposal_id,
                status=DecisionStatus.REJECTED,
                provider="none",
                validation_messages=("provider_not_configured",),
            )
        return self.provider.preflight_multileg(proposal)

    def execute(self, request: ExecutionRequest) -> ExecutionRecord:
        denial = self._deny_reason(request)
        if denial:
            return ExecutionRecord(
                execution_id=f"exec-{uuid4().hex}",
                request_id=request.request_id,
                proposal_id=request.proposal.proposal_id,
                mode=request.mode,
                status=DecisionStatus.REJECTED,
                reasons=(denial,),
            )
        if request.mode in {ExecutionMode.DRY_RUN, ExecutionMode.PAPER} or not self.config.live_trading_enabled:
            return ExecutionRecord(
                execution_id=f"exec-{uuid4().hex}",
                request_id=request.request_id,
                proposal_id=request.proposal.proposal_id,
                mode=ExecutionMode.DRY_RUN,
                status=DecisionStatus.APPROVED,
                reasons=("dry_run_record_created_no_provider_order",),
            )
        if self.provider is None:
            return ExecutionRecord(
                execution_id=f"exec-{uuid4().hex}",
                request_id=request.request_id,
                proposal_id=request.proposal.proposal_id,
                mode=request.mode,
                status=DecisionStatus.REJECTED,
                reasons=("provider_not_configured",),
            )
        return self.provider.place_multileg_order(request.proposal, idempotency_key=request.idempotency_key)

    def _deny_reason(self, request: ExecutionRequest) -> str | None:
        if not request.risk_decision.approved:
            return "risk_decision_not_approved"
        if self.config.kill_switch_enabled and request.mode == ExecutionMode.LIVE:
            return "kill_switch_enabled"
        if (
            request.mode == ExecutionMode.LIVE
            and self.config.require_operator_approval
            and not request.operator_approved
        ):
            return "operator_approval_required"
        if request.mode == ExecutionMode.LIVE and not self.config.live_trading_enabled:
            return "live_trading_disabled"
        if request.mode == ExecutionMode.LIVE and (request.preflight is None or not request.preflight.approved):
            return "preflight_not_approved"
        if not request.idempotency_key:
            return "missing_idempotency_key"
        return None
