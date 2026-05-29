from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

from regime_trader.schemas.learning import TradeJournalEntry
from regime_trader.schemas.regime import RegimeOutput
from regime_trader.schemas.trading import (
    ExecutionRecord,
    PreflightResult,
    RiskDecision,
    StrategyProposal,
)


class TradeJournal:
    def __init__(self) -> None:
        self.entries: dict[str, TradeJournalEntry] = {}

    def create(
        self,
        *,
        regime: RegimeOutput,
        proposal: StrategyProposal,
        risk_decision: RiskDecision,
        preflight: PreflightResult | None,
        execution: ExecutionRecord,
        thesis: str,
    ) -> TradeJournalEntry:
        entry = TradeJournalEntry(
            journal_id=f"journal-{uuid4().hex}",
            symbol=proposal.symbol,
            strategy_type=proposal.strategy_type,
            entry_regime_label=regime.regime_label,
            thesis=thesis,
            proposal_id=proposal.proposal_id,
            risk_decision_id=risk_decision.decision_id,
            preflight_id=preflight.preflight_id if preflight else None,
            execution_id=execution.execution_id,
            execution_mode=execution.mode,
            audit_event_ids=(),
        )
        self.entries[entry.journal_id] = entry
        return entry

    def close(self, journal_id: str, *, realized_pnl: Decimal) -> TradeJournalEntry:
        entry = self.entries[journal_id]
        updated = entry.model_copy(update={"realized_pnl": realized_pnl})
        self.entries[journal_id] = updated
        return updated
