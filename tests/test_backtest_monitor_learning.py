import sqlite3

from options_agno_team.config import AppConfig
from options_agno_team.models import ExecutionStatus
from options_agno_team.service import build_system


def test_backtest_records_metrics_and_persists_report(tmp_path) -> None:
    db_path = tmp_path / "audit.sqlite3"
    system = build_system(AppConfig(audit_db_path=str(db_path)))

    report = system.run_backtest(["BULL"], lookback=90, min_lookback=30, holding_period=5, step=10)

    assert report.trades
    assert report.win_rate >= 0
    assert report.average_return != 0
    assert report.regime_accuracy >= 0
    assert "BULL" in report.symbol_performance
    assert report.trades[0].original_thesis
    assert report.trades[0].outcome_vs_thesis
    assert report.regime_thesis_performance
    assert report.regime_thesis_insights

    with sqlite3.connect(db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM backtest_reports").fetchone()[0] == 1


def test_monitoring_and_learning_create_audit_records(tmp_path) -> None:
    db_path = tmp_path / "audit.sqlite3"
    system = build_system(AppConfig(audit_db_path=str(db_path)))
    proposal = system.propose_options_strategy("BULL", lookback=80)

    execution = system.execute_strategy(proposal.proposal_id)
    events = system.monitor_paper_positions()
    learning = system.reflect_trades()

    assert execution.status is ExecutionStatus.DRY_RUN
    assert events
    assert events[0].position_id == proposal.proposal_id
    assert learning.reflections
    assert learning.reflections[0].original_thesis
    assert learning.reflections[0].outcome_vs_thesis
    assert learning.performance_by_thesis
    assert learning.performance_by_regime_thesis
    assert learning.insights
    assert "regimes on BULL" in next(iter(learning.performance_by_regime_thesis))

    with sqlite3.connect(db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM monitoring_events").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM trade_reflections").fetchone()[0] == 1


def test_monitoring_loop_runs_repeated_refreshes_and_records_triggers(tmp_path) -> None:
    db_path = tmp_path / "audit.sqlite3"
    system = build_system(
        AppConfig(
            audit_db_path=str(db_path),
            max_entropy_for_entry=0.0,
            max_position_delta_abs=0.0,
        )
    )
    proposal = system.propose_options_strategy("BULL", lookback=80)
    system.execute_strategy(proposal.proposal_id)

    batches = system.monitor_paper_positions_loop(iterations=2, interval_seconds=0)

    assert len(batches) == 2
    assert all(batch for batch in batches)
    assert "high_entropy_spike" in batches[0][0].triggers
    assert "delta_drift" in batches[0][0].triggers
    with sqlite3.connect(db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM monitoring_events").fetchone()[0] == 2
        assert conn.execute("SELECT COUNT(*) FROM alert_events").fetchone()[0] == 2


def test_public_dry_run_preflight_calls_public_without_live_order_flag() -> None:
    from unittest.mock import MagicMock

    from options_agno_team.adapters.fixture import FixtureMarketDataAdapter
    from options_agno_team.config import DataMode
    from options_agno_team.execution import ExecutionGateway
    from options_agno_team.features import FeatureEngine
    from options_agno_team.regime import RegimeEngine
    from options_agno_team.risk import RiskEngine
    from options_agno_team.strategy import StrategyEngine

    adapter = FixtureMarketDataAdapter()
    features = FeatureEngine().build("BULL", adapter.get_bars("BULL", lookback=80))
    regime = RegimeEngine().classify(features)
    proposal = StrategyEngine(adapter).propose(regime)
    risk = RiskEngine(adapter).evaluate(proposal)
    public_client = MagicMock()
    public_client.preflight_put_credit_spread.return_value = {"ok": True}
    gateway = ExecutionGateway(
        config=AppConfig(data_mode=DataMode.PUBLIC),
        public_client=public_client,
    )

    result = gateway.preflight(proposal, risk)

    assert result.status.value == "preflighted"
    public_client.preflight_put_credit_spread.assert_called_once()
    assert public_client.method_calls[0][0].startswith("preflight_")
