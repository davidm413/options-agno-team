"""Deterministic portfolio and order risk checks."""

from __future__ import annotations

from options_agno_team.adapters.base import MarketDataAdapter
from options_agno_team.config import AppConfig, ExecutionMode
from options_agno_team.models import RiskDecision, RiskStatus, StrategyProposal


class RiskEngine:
    def __init__(self, adapter: MarketDataAdapter, config: AppConfig | None = None) -> None:
        self.adapter = adapter
        self.config = config or AppConfig()

    def evaluate(self, proposal: StrategyProposal) -> RiskDecision:
        account = self.adapter.get_account()
        equity = float(account.get("equity", 0.0))
        buying_power = float(account.get("buying_power", 0.0))
        base_delta = float(account.get("portfolio_delta", 0.0))
        day_pnl = float(account.get("day_pnl", account.get("daily_pnl", 0.0)) or 0.0)
        trades_today = int(account.get("trades_today", 0) or 0)
        open_trades = len(self.adapter.get_positions())
        risk_budget = equity * self.config.max_risk_per_trade
        proposal_delta = _proposal_delta(proposal)
        portfolio_delta_after = base_delta + proposal_delta
        reasons: list[str] = []

        if self.config.kill_switch_enabled:
            reasons.append("kill switch is enabled")
        if day_pnl <= -abs(self.config.daily_loss_limit):
            reasons.append(
                f"day_pnl {day_pnl:.2f} breaches daily_loss_limit {self.config.daily_loss_limit:.2f}"
            )
        if open_trades >= self.config.max_open_trades:
            reasons.append(
                f"open_trades {open_trades} meets or exceeds max_open_trades {self.config.max_open_trades}"
            )
        if trades_today >= self.config.max_trades_per_day:
            reasons.append(
                f"trades_today {trades_today} meets or exceeds max_trades_per_day {self.config.max_trades_per_day}"
            )
        if proposal.max_loss > risk_budget:
            reasons.append(
                f"max_loss {proposal.max_loss:.2f} exceeds risk_budget {risk_budget:.2f}"
            )
        if proposal.max_loss > buying_power:
            reasons.append(
                f"max_loss {proposal.max_loss:.2f} exceeds buying_power {buying_power:.2f}"
            )
        if proposal.regime.confidence < self.config.min_regime_confidence:
            reasons.append(
                f"confidence {proposal.regime.confidence:.2f} below minimum {self.config.min_regime_confidence:.2f}"
            )
        if proposal.regime.entropy > self.config.max_entropy_for_entry:
            reasons.append(
                f"entropy {proposal.regime.entropy:.2f} above maximum {self.config.max_entropy_for_entry:.2f}"
            )
        if abs(portfolio_delta_after) > self.config.max_portfolio_delta:
            reasons.append(
                f"portfolio_delta_after {portfolio_delta_after:.4f} exceeds limit {self.config.max_portfolio_delta:.4f}"
            )
        if (
            self.config.execution_mode is ExecutionMode.LIVE
            and proposal.strategy_type.value not in self.config.allowed_live_strategies
        ):
            reasons.append(f"{proposal.strategy_type.value} is not live-enabled")

        approved = not reasons
        if approved:
            reasons.append("approved")
        return RiskDecision(
            proposal_id=proposal.proposal_id,
            status=RiskStatus.APPROVED if approved else RiskStatus.REJECTED,
            approved=approved,
            reasons=tuple(reasons),
            max_loss=proposal.max_loss,
            risk_budget=risk_budget,
            portfolio_delta_after=round(portfolio_delta_after, 6),
        )


def _proposal_delta(proposal: StrategyProposal) -> float:
    buy_count = sum(1 for leg in proposal.legs if leg.side.value == "buy")
    sell_count = sum(1 for leg in proposal.legs if leg.side.value == "sell")
    directional_hint = 0.0
    if "bull" in proposal.strategy_type.value:
        directional_hint = 0.01
    elif "bear" in proposal.strategy_type.value:
        directional_hint = -0.01
    return directional_hint + (buy_count - sell_count) * 0.002
