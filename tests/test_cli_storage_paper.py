import json
import sqlite3

from options_agno_team import cli
from options_agno_team.config import AppConfig
from options_agno_team.models import ExecutionStatus
from options_agno_team.service import build_system


def test_cli_persists_proposal_across_commands(tmp_path, capsys) -> None:
    db_path = tmp_path / "audit.sqlite3"

    assert cli.main(["--db", str(db_path), "propose-strategy", "BULL"]) == 0
    proposal = json.loads(capsys.readouterr().out)

    assert cli.main(["--db", str(db_path), "check-risk", proposal["proposal_id"]]) == 0
    risk = json.loads(capsys.readouterr().out)

    assert risk["proposal_id"] == proposal["proposal_id"]
    assert risk["approved"] is True


def test_sqlite_audit_records_core_events_and_paper_position(tmp_path) -> None:
    db_path = tmp_path / "audit.sqlite3"
    system = build_system(AppConfig(audit_db_path=str(db_path)))

    regime = system.detect_regime("BULL")
    proposal = system.propose_options_strategy("BULL")
    risk = system.check_portfolio_risk(proposal.proposal_id)
    preflight = system.preflight_strategy(proposal.proposal_id)
    execution = system.execute_strategy(proposal.proposal_id)
    positions = system.list_paper_positions()

    assert regime.symbol == "BULL"
    assert risk.approved is True
    assert preflight.status is ExecutionStatus.DRY_RUN
    assert execution.status is ExecutionStatus.DRY_RUN
    assert positions[0].proposal_id == proposal.proposal_id

    with sqlite3.connect(db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM regime_snapshots").fetchone()[0] >= 1
        assert conn.execute("SELECT COUNT(*) FROM proposals").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM risk_decisions").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM executions").fetchone()[0] == 2
        assert conn.execute("SELECT COUNT(*) FROM paper_positions").fetchone()[0] == 1


def test_mark_to_market_refreshes_open_paper_positions(tmp_path) -> None:
    system = build_system(AppConfig(audit_db_path=str(tmp_path / "audit.sqlite3")))
    proposal = system.propose_options_strategy("BULL")

    system.execute_strategy(proposal.proposal_id)
    marked = system.mark_to_market()

    assert marked
    assert marked[0].proposal_id == proposal.proposal_id


def test_cli_exposes_backtest_monitoring_and_learning(tmp_path, capsys) -> None:
    db_path = tmp_path / "audit.sqlite3"

    assert cli.main(["--db", str(db_path), "rank-candidates", "BULL", "BEAR"]) == 0
    ranked = json.loads(capsys.readouterr().out)
    assert ranked[0]["rank"] == 1

    assert (
        cli.main(
            [
                "--db",
                str(db_path),
                "backtest",
                "BULL",
                "--lookback",
                "90",
                "--min-lookback",
                "30",
                "--holding-period",
                "5",
                "--step",
                "10",
            ]
        )
        == 0
    )
    backtest = json.loads(capsys.readouterr().out)
    assert backtest["trades"]

    assert cli.main(["--db", str(db_path), "propose-strategy", "BULL", "--lookback", "80"]) == 0
    proposal = json.loads(capsys.readouterr().out)
    assert cli.main(["--db", str(db_path), "execute", proposal["proposal_id"]]) == 0
    capsys.readouterr()

    assert cli.main(["--db", str(db_path), "monitor-once"]) == 0
    monitor = json.loads(capsys.readouterr().out)
    assert monitor

    assert cli.main(["--db", str(db_path), "reflect-trades"]) == 0
    reflections = json.loads(capsys.readouterr().out)
    assert reflections["reflections"]
