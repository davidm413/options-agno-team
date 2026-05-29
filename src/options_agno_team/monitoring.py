"""Monitoring pass for open paper positions."""

from __future__ import annotations

import time
from datetime import date, datetime, timezone
from uuid import NAMESPACE_URL, uuid5

from options_agno_team.adapters.base import MarketDataAdapter
from options_agno_team.config import AppConfig
from options_agno_team.execution import ProposalRepository
from options_agno_team.features import FeatureEngine
from options_agno_team.models import MonitoringEvent, OrderLeg, OrderSide, PaperPosition, RegimeSnapshot
from options_agno_team.paper import PaperTradingService
from options_agno_team.regime import RegimeEngine


class MonitoringService:
    def __init__(
        self,
        adapter: MarketDataAdapter,
        repository: ProposalRepository,
        paper_trading: PaperTradingService,
        config: AppConfig | None = None,
        *,
        feature_engine: FeatureEngine | None = None,
        regime_engine: RegimeEngine | None = None,
    ) -> None:
        self.adapter = adapter
        self.repository = repository
        self.paper_trading = paper_trading
        self.config = config or AppConfig()
        self.feature_engine = feature_engine or FeatureEngine()
        self.regime_engine = regime_engine or RegimeEngine()

    def run_once(self) -> list[MonitoringEvent]:
        marked_positions = self.paper_trading.mark_to_market()
        events: list[MonitoringEvent] = []
        for position in marked_positions:
            timestamp = datetime.now(timezone.utc)
            proposal = self.repository.get_proposal(position.proposal_id)
            current_regime = self._current_regime(position.symbol)
            self.repository.save_regime_snapshot(current_regime)
            net_delta = _net_delta(self.adapter, position, list(proposal.legs))
            capital_at_risk = max(proposal.max_loss, 1.0)
            pnl_pct = position.unrealized_pnl / capital_at_risk
            triggers = _exit_triggers(
                position,
                current_regime,
                original_regime=proposal.regime,
                net_delta=net_delta,
                pnl_pct=pnl_pct,
                min_dte=_days_to_expiration(list(proposal.legs), as_of=timestamp.date()),
                config=self.config,
                as_of=timestamp,
            )
            action = "exit_review" if triggers else "hold"
            notes = (
                f"entry_net={position.entry_net_price:.2f}",
                f"mark_net={position.mark_net_price:.2f}",
                f"capital_at_risk={capital_at_risk:.2f}",
                f"current_confidence={current_regime.confidence:.2f}",
            )
            event = MonitoringEvent(
                event_id=str(uuid5(NAMESPACE_URL, f"monitor:{position.position_id}:{timestamp.isoformat()}")),
                position_id=position.position_id,
                proposal_id=position.proposal_id,
                symbol=position.symbol,
                timestamp=timestamp,
                action=action,
                triggers=tuple(triggers),
                original_regime_label=proposal.regime.regime_label,
                current_regime_label=current_regime.regime_label,
                unrealized_pnl=position.unrealized_pnl,
                pnl_pct_of_risk=round(pnl_pct, 6),
                net_delta=round(net_delta, 6),
                entropy=current_regime.entropy,
                notes=notes,
            )
            self.repository.save_monitoring_event(event)
            events.append(event)
        return events

    def run_loop(self, *, iterations: int = 3, interval_seconds: float = 60.0) -> list[list[MonitoringEvent]]:
        batches: list[list[MonitoringEvent]] = []
        total_iterations = max(iterations, 1)
        sleep_seconds = max(interval_seconds, 0.0)
        for index in range(total_iterations):
            batches.append(self.run_once())
            if index < total_iterations - 1:
                time.sleep(sleep_seconds)
        return batches

    def _current_regime(self, symbol: str) -> RegimeSnapshot:
        bars = self.adapter.get_bars(symbol, lookback=120)
        chain = self.adapter.get_option_chain(symbol)
        features = self.feature_engine.build(symbol, bars, option_chain=chain)
        return self.regime_engine.classify(features)


def _exit_triggers(
    position: PaperPosition,
    current_regime: RegimeSnapshot,
    *,
    original_regime: RegimeSnapshot,
    net_delta: float,
    pnl_pct: float,
    min_dte: int,
    config: AppConfig,
    as_of: datetime | None = None,
) -> list[str]:
    current_time = as_of or datetime.now(timezone.utc)
    triggers: list[str] = []
    if pnl_pct >= config.profit_target_pct:
        triggers.append("profit_target")
    if pnl_pct <= -config.stop_loss_pct:
        triggers.append("stop_loss")
    if min_dte <= config.time_decay_exit_dte:
        triggers.append("time_decay")
    if (current_time - position.opened_at).days >= config.max_days_in_trade:
        triggers.append("max_days_in_trade")
    if current_regime.directional_bias is not original_regime.directional_bias:
        triggers.append("regime_flip")
    if abs(net_delta) > config.max_position_delta_abs:
        triggers.append("delta_drift")
    entropy_jump = current_regime.entropy - original_regime.entropy
    if current_regime.entropy > config.max_entropy_for_entry or entropy_jump >= config.entropy_spike_delta:
        triggers.append("high_entropy_spike")
    return triggers


def _net_delta(adapter: MarketDataAdapter, position: PaperPosition, legs: list[OrderLeg]) -> float:
    greeks = adapter.get_option_greeks([leg.contract_symbol for leg in legs])
    total = 0.0
    for leg in legs:
        delta = greeks.get(leg.contract_symbol, {}).get("delta")
        if delta is None:
            continue
        multiplier = 1.0 if leg.side is OrderSide.BUY else -1.0
        total += float(delta) * multiplier * leg.quantity
    return total


def _days_to_expiration(legs: list[OrderLeg], *, as_of: date | None = None) -> int:
    expirations: list[date] = []
    for leg in legs:
        try:
            expirations.append(date.fromisoformat(leg.expiration_date))
        except ValueError:
            continue
    if not expirations:
        return 999
    current_date = as_of or date.today()
    return min((expiration - current_date).days for expiration in expirations)
