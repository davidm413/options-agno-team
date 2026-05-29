from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

from regime_trader.config.models import RiskConfig
from regime_trader.schemas.market import Account, Position
from regime_trader.schemas.trading import (
    DecisionStatus,
    RiskDecision,
    StrategyProposal,
    StrategyType,
)


class RiskEngine:
    def __init__(self, config: RiskConfig) -> None:
        self.config = config

    def review(
        self,
        proposal: StrategyProposal,
        *,
        account: Account,
        positions: tuple[Position, ...] = (),
        open_trade_count: int = 0,
    ) -> RiskDecision:
        reasons: list[str] = []
        evaluated = {
            "max_loss_per_trade": str(self.config.max_loss_per_trade),
            "max_buying_power_fraction": str(self.config.max_buying_power_fraction),
            "max_open_trades": str(self.config.max_open_trades),
            "require_defined_max_loss": str(self.config.require_defined_max_loss),
        }
        if proposal.strategy_type == StrategyType.NO_TRADE:
            reasons.append("proposal_is_no_trade")
        if self.config.require_defined_max_loss and proposal.max_loss is None:
            reasons.append("undefined_max_loss")
        if proposal.max_loss is not None and proposal.max_loss > self.config.max_loss_per_trade:
            reasons.append("max_loss_exceeds_limit")
        buying_power_limit = account.buying_power * self.config.max_buying_power_fraction
        if proposal.max_loss is not None and proposal.max_loss > buying_power_limit:
            reasons.append("max_loss_exceeds_buying_power_fraction")
        if open_trade_count >= self.config.max_open_trades:
            reasons.append("open_trade_limit_reached")
        portfolio_delta = sum(
            (position.greeks.delta or 0) * float(position.quantity) for position in positions if position.greeks
        )
        proposed_delta = proposal.exposure_delta or 0.0
        if abs(portfolio_delta + proposed_delta) > self.config.max_portfolio_delta_abs:
            reasons.append("portfolio_delta_limit_exceeded")
        status = DecisionStatus.REJECTED if reasons else DecisionStatus.APPROVED
        return RiskDecision(
            decision_id=f"risk-{uuid4().hex}",
            proposal_id=proposal.proposal_id,
            status=status,
            approved_quantity=0 if reasons else 1,
            reasons=tuple(reasons or ["within_configured_limits"]),
            evaluated_limits=evaluated,
            config_version=proposal.config_version,
        )


def position_market_value(positions: tuple[Position, ...], symbol: str) -> Decimal:
    return sum(
        (position.market_value or Decimal("0") for position in positions if position.symbol == symbol),
        Decimal("0"),
    )
