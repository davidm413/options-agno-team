"""SQLite audit storage for proposals, decisions, executions, and paper positions."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from options_agno_team.execution import ProposalRepository
from options_agno_team.models import (
    AlertEvent,
    BacktestReport,
    DirectionalBias,
    ExecutionResult,
    ExecutionStatus,
    FeatureSnapshot,
    MonitoringEvent,
    OptionType,
    OrderIntent,
    OrderLeg,
    OrderSide,
    PaperPosition,
    RegimeSnapshot,
    RiskDecision,
    RiskStatus,
    StrategyProposal,
    StrategyType,
    TradeReflection,
    VolatilityRegime,
    to_jsonable,
)


class SQLiteAuditRepository(ProposalRepository):
    """ProposalRepository implementation backed by a local SQLite audit database."""

    def __init__(self, db_path: str | Path) -> None:
        super().__init__()
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def save_regime_snapshot(self, snapshot: RegimeSnapshot) -> None:
        super().save_regime_snapshot(snapshot)
        payload = _json_payload(snapshot)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO regime_snapshots (symbol, timestamp, regime_label, payload_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    snapshot.symbol,
                    snapshot.timestamp.isoformat(),
                    snapshot.regime_label,
                    payload,
                    _now_iso(),
                ),
            )

    def save_proposal(self, proposal: StrategyProposal) -> None:
        super().save_proposal(proposal)
        payload = _json_payload(proposal)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO proposals (
                    proposal_id, symbol, strategy_type, payload_json, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(proposal_id) DO UPDATE SET
                    symbol=excluded.symbol,
                    strategy_type=excluded.strategy_type,
                    payload_json=excluded.payload_json,
                    updated_at=excluded.updated_at
                """,
                (
                    proposal.proposal_id,
                    proposal.symbol,
                    proposal.strategy_type.value,
                    payload,
                    _now_iso(),
                    _now_iso(),
                ),
            )

    def save_risk_decision(self, decision: RiskDecision) -> None:
        super().save_risk_decision(decision)
        payload = _json_payload(decision)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO risk_decisions (
                    proposal_id, status, approved, payload_json, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(proposal_id) DO UPDATE SET
                    status=excluded.status,
                    approved=excluded.approved,
                    payload_json=excluded.payload_json,
                    updated_at=excluded.updated_at
                """,
                (
                    decision.proposal_id,
                    decision.status.value,
                    int(decision.approved),
                    payload,
                    _now_iso(),
                    _now_iso(),
                ),
            )

    def save_execution_result(self, result: ExecutionResult) -> None:
        super().save_execution_result(result)
        payload = _json_payload(result)
        live_attempt = result.status is not ExecutionStatus.DRY_RUN
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO executions (
                    proposal_id, status, live_attempt, payload_json, created_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    result.proposal_id,
                    result.status.value,
                    int(live_attempt),
                    payload,
                    _now_iso(),
                ),
            )

    def save_paper_position(self, position: PaperPosition) -> None:
        super().save_paper_position(position)
        payload = _json_payload(position)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO paper_positions (
                    position_id, proposal_id, symbol, status, payload_json, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(position_id) DO UPDATE SET
                    status=excluded.status,
                    payload_json=excluded.payload_json,
                    updated_at=excluded.updated_at
                """,
                (
                    position.position_id,
                    position.proposal_id,
                    position.symbol,
                    position.status,
                    payload,
                    position.opened_at.isoformat(),
                    position.updated_at.isoformat(),
                ),
            )

    def save_backtest_report(self, report: BacktestReport) -> None:
        super().save_backtest_report(report)
        payload = _json_payload(report)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO backtest_reports (
                    report_id, symbols, win_rate, max_drawdown, payload_json, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(report_id) DO UPDATE SET
                    symbols=excluded.symbols,
                    win_rate=excluded.win_rate,
                    max_drawdown=excluded.max_drawdown,
                    payload_json=excluded.payload_json
                """,
                (
                    report.report_id,
                    ",".join(report.symbols),
                    report.win_rate,
                    report.max_drawdown,
                    payload,
                    _now_iso(),
                ),
            )

    def save_monitoring_event(self, event: MonitoringEvent) -> None:
        super().save_monitoring_event(event)
        payload = _json_payload(event)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO monitoring_events (
                    event_id, position_id, proposal_id, symbol, action, payload_json, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(event_id) DO UPDATE SET
                    action=excluded.action,
                    payload_json=excluded.payload_json
                """,
                (
                    event.event_id,
                    event.position_id,
                    event.proposal_id,
                    event.symbol,
                    event.action,
                    payload,
                    event.timestamp.isoformat(),
                ),
            )

    def save_trade_reflection(self, reflection: TradeReflection) -> None:
        super().save_trade_reflection(reflection)
        payload = _json_payload(reflection)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO trade_reflections (
                    reflection_id, position_id, proposal_id, symbol, outcome, payload_json, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(reflection_id) DO UPDATE SET
                    outcome=excluded.outcome,
                    payload_json=excluded.payload_json
                """,
                (
                    reflection.reflection_id,
                    reflection.position_id,
                    reflection.proposal_id,
                    reflection.symbol,
                    reflection.outcome,
                    payload,
                    reflection.timestamp.isoformat(),
                ),
            )

    def save_alert_event(self, event: AlertEvent) -> None:
        super().save_alert_event(event)
        payload = _json_payload(event)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO alert_events (
                    alert_id, severity, category, proposal_id, symbol, payload_json, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(alert_id) DO UPDATE SET
                    severity=excluded.severity,
                    category=excluded.category,
                    payload_json=excluded.payload_json
                """,
                (
                    event.alert_id,
                    event.severity.value,
                    event.category,
                    event.proposal_id,
                    event.symbol,
                    payload,
                    event.timestamp.isoformat(),
                ),
            )

    def list_paper_positions(self, *, open_only: bool = True) -> list[PaperPosition]:
        query = "SELECT payload_json FROM paper_positions"
        params: tuple[Any, ...] = ()
        if open_only:
            query += " WHERE status = ?"
            params = ("open",)
        query += " ORDER BY created_at"
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        positions = [_paper_position_from_payload(json.loads(row["payload_json"])) for row in rows]
        self.paper_positions = {position.position_id: position for position in positions}
        return positions

    def get_proposal(self, proposal_id: str) -> StrategyProposal:
        if proposal_id in self.proposals:
            return self.proposals[proposal_id]
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload_json FROM proposals WHERE proposal_id = ?",
                (proposal_id,),
            ).fetchone()
        if row is None:
            raise KeyError(proposal_id)
        proposal = _proposal_from_payload(json.loads(row["payload_json"]))
        self.proposals[proposal.proposal_id] = proposal
        return proposal

    def get_risk_decision(self, proposal_id: str) -> RiskDecision:
        if proposal_id in self.risk_decisions:
            return self.risk_decisions[proposal_id]
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload_json FROM risk_decisions WHERE proposal_id = ?",
                (proposal_id,),
            ).fetchone()
        if row is None:
            raise KeyError(proposal_id)
        decision = _risk_decision_from_payload(json.loads(row["payload_json"]))
        self.risk_decisions[proposal_id] = decision
        return decision

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _initialize(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS regime_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    regime_label TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_regime_snapshots_symbol_created
                    ON regime_snapshots(symbol, created_at);

                CREATE TABLE IF NOT EXISTS proposals (
                    proposal_id TEXT PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    strategy_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS risk_decisions (
                    proposal_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    approved INTEGER NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS executions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    proposal_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    live_attempt INTEGER NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_executions_proposal_created
                    ON executions(proposal_id, created_at);

                CREATE TABLE IF NOT EXISTS paper_positions (
                    position_id TEXT PRIMARY KEY,
                    proposal_id TEXT NOT NULL UNIQUE,
                    symbol TEXT NOT NULL,
                    status TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS backtest_reports (
                    report_id TEXT PRIMARY KEY,
                    symbols TEXT NOT NULL,
                    win_rate REAL NOT NULL,
                    max_drawdown REAL NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS monitoring_events (
                    event_id TEXT PRIMARY KEY,
                    position_id TEXT NOT NULL,
                    proposal_id TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    action TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_monitoring_events_position_created
                    ON monitoring_events(position_id, created_at);

                CREATE TABLE IF NOT EXISTS trade_reflections (
                    reflection_id TEXT PRIMARY KEY,
                    position_id TEXT NOT NULL,
                    proposal_id TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_trade_reflections_symbol_created
                    ON trade_reflections(symbol, created_at);

                CREATE TABLE IF NOT EXISTS alert_events (
                    alert_id TEXT PRIMARY KEY,
                    severity TEXT NOT NULL,
                    category TEXT NOT NULL,
                    proposal_id TEXT,
                    symbol TEXT,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_alert_events_category_created
                    ON alert_events(category, created_at);
                """
            )


def _json_payload(value: Any) -> str:
    return json.dumps(to_jsonable(value), sort_keys=True, separators=(",", ":"))


def _feature_from_payload(data: dict[str, Any]) -> FeatureSnapshot:
    return FeatureSnapshot(
        symbol=data["symbol"],
        timestamp=_datetime_from_payload(data["timestamp"]),
        returns=tuple(float(value) for value in data["returns"]),
        realized_volatility=float(data["realized_volatility"]),
        wasserstein_distance=float(data["wasserstein_distance"]),
        entropy=float(data["entropy"]),
        momentum=float(data["momentum"]),
        iv_rank=_optional_float(data.get("iv_rank")),
        skew=_optional_float(data.get("skew")),
        term_structure_slope=_optional_float(data.get("term_structure_slope")),
        feature_vector=tuple(float(value) for value in data["feature_vector"]),
    )


def _regime_from_payload(data: dict[str, Any]) -> RegimeSnapshot:
    return RegimeSnapshot(
        symbol=data["symbol"],
        timestamp=_datetime_from_payload(data["timestamp"]),
        volatility_regime=VolatilityRegime(data["volatility_regime"]),
        directional_bias=DirectionalBias(data["directional_bias"]),
        regime_label=data["regime_label"],
        cluster_id=int(data["cluster_id"]),
        confidence=float(data["confidence"]),
        wasserstein_distance=float(data["wasserstein_distance"]),
        entropy=float(data["entropy"]),
        key_drivers=tuple(data["key_drivers"]),
        transition_probability={str(k): float(v) for k, v in data["transition_probability"].items()},
        features=_feature_from_payload(data["features"]),
    )


def _leg_from_payload(data: dict[str, Any]) -> OrderLeg:
    return OrderLeg(
        contract_symbol=data["contract_symbol"],
        side=OrderSide(data["side"]),
        option_type=OptionType(data["option_type"]),
        strike=float(data["strike"]),
        expiration_date=data["expiration_date"],
        quantity=int(data["quantity"]),
    )


def _proposal_from_payload(data: dict[str, Any]) -> StrategyProposal:
    return StrategyProposal(
        proposal_id=data["proposal_id"],
        symbol=data["symbol"],
        strategy_type=StrategyType(data["strategy_type"]),
        regime=_regime_from_payload(data["regime"]),
        quantity=int(data["quantity"]),
        legs=tuple(_leg_from_payload(leg) for leg in data["legs"]),
        estimated_credit=_optional_float(data.get("estimated_credit")),
        estimated_debit=_optional_float(data.get("estimated_debit")),
        max_loss=float(data["max_loss"]),
        rationale=tuple(data["rationale"]),
        is_live_capable=bool(data["is_live_capable"]),
    )


def _risk_decision_from_payload(data: dict[str, Any]) -> RiskDecision:
    return RiskDecision(
        proposal_id=data["proposal_id"],
        status=RiskStatus(data["status"]),
        approved=bool(data["approved"]),
        reasons=tuple(data["reasons"]),
        max_loss=float(data["max_loss"]),
        risk_budget=float(data["risk_budget"]),
        portfolio_delta_after=float(data["portfolio_delta_after"]),
    )


def _order_intent_from_payload(data: dict[str, Any] | None) -> OrderIntent | None:
    if data is None:
        return None
    return OrderIntent(
        proposal_id=data["proposal_id"],
        strategy_type=StrategyType(data["strategy_type"]),
        symbol=data["symbol"],
        quantity=int(data["quantity"]),
        legs=tuple(_leg_from_payload(leg) for leg in data["legs"]),
        limit_price=float(data["limit_price"]),
    )


def _execution_result_from_payload(data: dict[str, Any]) -> ExecutionResult:
    return ExecutionResult(
        proposal_id=data["proposal_id"],
        status=ExecutionStatus(data["status"]),
        message=data["message"],
        order_intent=_order_intent_from_payload(data.get("order_intent")),
        preflight=data.get("preflight"),
        order_id=data.get("order_id"),
        audit=tuple(data["audit"]),
    )


def _paper_position_from_payload(data: dict[str, Any]) -> PaperPosition:
    return PaperPosition(
        position_id=data["position_id"],
        proposal_id=data["proposal_id"],
        symbol=data["symbol"],
        strategy_type=StrategyType(data["strategy_type"]),
        quantity=int(data["quantity"]),
        opened_at=_datetime_from_payload(data["opened_at"]),
        updated_at=_datetime_from_payload(data["updated_at"]),
        entry_net_price=float(data["entry_net_price"]),
        mark_net_price=float(data["mark_net_price"]),
        unrealized_pnl=float(data["unrealized_pnl"]),
        status=data["status"],
    )


def _datetime_from_payload(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
