"""Simple paper-trading lifecycle for dry-run executions."""

from __future__ import annotations

from datetime import datetime, timezone

from options_agno_team.adapters.base import MarketDataAdapter
from options_agno_team.execution import ProposalRepository
from options_agno_team.models import (
    ExecutionResult,
    ExecutionStatus,
    OptionContractQuote,
    OrderSide,
    PaperPosition,
    StrategyProposal,
)


class PaperTradingService:
    def __init__(self, adapter: MarketDataAdapter, repository: ProposalRepository) -> None:
        self.adapter = adapter
        self.repository = repository

    def open_from_dry_run(
        self, proposal: StrategyProposal, execution: ExecutionResult
    ) -> PaperPosition | None:
        if execution.status is not ExecutionStatus.DRY_RUN or execution.order_intent is None:
            return None
        entry_net = _entry_net_price(proposal)
        mark_net = self._mark_net_price(proposal)
        position = _position(proposal, entry_net=entry_net, mark_net=mark_net)
        self.repository.save_paper_position(position)
        return position

    def list_positions(self, *, open_only: bool = True) -> list[PaperPosition]:
        return self.repository.list_paper_positions(open_only=open_only)

    def mark_to_market(self) -> list[PaperPosition]:
        updated: list[PaperPosition] = []
        for position in self.repository.list_paper_positions(open_only=True):
            proposal = self.repository.get_proposal(position.proposal_id)
            mark_net = self._mark_net_price(proposal)
            refreshed = _position(
                proposal,
                entry_net=position.entry_net_price,
                mark_net=mark_net,
                opened_at=position.opened_at,
            )
            self.repository.save_paper_position(refreshed)
            updated.append(refreshed)
        return updated

    def _mark_net_price(self, proposal: StrategyProposal) -> float:
        expirations = sorted({leg.expiration_date for leg in proposal.legs})
        quotes: dict[str, OptionContractQuote] = {}
        for expiration in expirations:
            chain = self.adapter.get_option_chain(proposal.symbol, expiration_date=expiration)
            quotes.update({contract.symbol: contract for contract in chain})

        net_price = 0.0
        for leg in proposal.legs:
            quote = quotes.get(leg.contract_symbol)
            if quote is None:
                raise KeyError(f"Missing option quote for {leg.contract_symbol}")
            mid = quote.mid if quote.mid is not None else quote.last
            if mid is None:
                raise ValueError(f"Missing mark price for {leg.contract_symbol}")
            multiplier = 1.0 if leg.side is OrderSide.BUY else -1.0
            net_price += multiplier * float(mid)
        return round(net_price, 2)


def _entry_net_price(proposal: StrategyProposal) -> float:
    if proposal.estimated_debit is not None:
        return round(float(proposal.estimated_debit), 2)
    if proposal.estimated_credit is not None:
        return round(-float(proposal.estimated_credit), 2)
    return 0.0


def _position(
    proposal: StrategyProposal,
    *,
    entry_net: float,
    mark_net: float,
    opened_at: datetime | None = None,
) -> PaperPosition:
    now = datetime.now(timezone.utc)
    open_time = opened_at or now
    pnl = round((mark_net - entry_net) * 100 * proposal.quantity, 2)
    return PaperPosition(
        position_id=proposal.proposal_id,
        proposal_id=proposal.proposal_id,
        symbol=proposal.symbol,
        strategy_type=proposal.strategy_type,
        quantity=proposal.quantity,
        opened_at=open_time,
        updated_at=now,
        entry_net_price=entry_net,
        mark_net_price=mark_net,
        unrealized_pnl=pnl,
    )
