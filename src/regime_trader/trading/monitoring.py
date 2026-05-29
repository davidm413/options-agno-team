from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

from regime_trader.schemas.market import Position
from regime_trader.schemas.regime import RegimeOutput
from regime_trader.schemas.trading import MonitoringAlert, MonitoringSnapshot


class PositionMonitor:
    def evaluate(
        self,
        *,
        position: Position,
        entry_regime: RegimeOutput,
        current_regime: RegimeOutput,
        max_loss_alert: Decimal,
    ) -> MonitoringSnapshot:
        alerts: list[MonitoringAlert] = []
        rationale: list[str] = []
        recommendation = "hold"
        if current_regime.directional_bias != entry_regime.directional_bias:
            alerts.append(
                MonitoringAlert(
                    alert_id=f"alert-{uuid4().hex}",
                    symbol=position.symbol,
                    severity="medium",
                    reason="regime_thesis_drift",
                )
            )
            recommendation = "review_close_or_hedge"
            rationale.append("current regime conflicts with entry thesis")
        if position.unrealized_pnl is not None and position.unrealized_pnl <= -abs(max_loss_alert):
            alerts.append(
                MonitoringAlert(
                    alert_id=f"alert-{uuid4().hex}",
                    symbol=position.symbol,
                    severity="high",
                    reason="pnl_risk_breach",
                )
            )
            recommendation = "review_close"
            rationale.append("unrealized loss breached configured alert threshold")
        return MonitoringSnapshot(
            symbol=position.symbol,
            timestamp=current_regime.timestamp,
            position_status="open",
            pnl=position.unrealized_pnl,
            greeks=position.greeks,
            recommendation=recommendation,
            rationale=tuple(rationale or ["within_monitoring_thresholds"]),
            alerts=tuple(alerts),
        )
