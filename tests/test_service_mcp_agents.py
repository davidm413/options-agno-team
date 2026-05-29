import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

from options_agno_team.agents import build_agent_specs
from options_agno_team.config import AppConfig, DataMode
from options_agno_team.mcp_server import build_tool_handlers
from options_agno_team.models import ExecutionStatus
from options_agno_team.service import build_system


def test_service_full_fixture_flow() -> None:
    system = build_system()

    proposal = system.propose_options_strategy("BULL")
    ranked = system.rank_trade_candidates(["BULL", "BEAR"])
    risk = system.check_portfolio_risk(proposal.proposal_id)
    result = system.execute_strategy(proposal.proposal_id)

    assert [candidate.rank for candidate in ranked] == [1, 2]
    assert all(candidate.rationale for candidate in ranked)
    assert risk.approved is True
    assert result.status is ExecutionStatus.DRY_RUN


def test_public_system_reuses_adapter_client_for_real_dry_run_preflight(monkeypatch) -> None:
    public_client = MagicMock()
    fake_sdk = SimpleNamespace(
        ApiKeyAuthConfig=MagicMock(return_value=object()),
        PublicApiClientConfiguration=MagicMock(return_value=object()),
        PublicApiClient=MagicMock(return_value=public_client),
    )
    monkeypatch.setitem(sys.modules, "public_api_sdk", fake_sdk)

    system = build_system(
        AppConfig(data_mode=DataMode.PUBLIC, public_api_secret_key="secret"),
    )

    assert system.execution_gateway.public_client is public_client


def test_mcp_tool_handlers_return_jsonable_payloads() -> None:
    system = build_system()
    handlers = build_tool_handlers(system)

    regime = handlers["detect_regime"]("BULL")
    ranked = handlers["rank_trade_candidates"](["BULL"])
    proposal = handlers["propose_options_strategy"]("BULL")
    risk = handlers["check_portfolio_risk"](proposal["proposal_id"])
    readiness = handlers["live_readiness"]()
    result = handlers["preflight_strategy"](proposal["proposal_id"])
    execution = handlers["execute_strategy"](proposal["proposal_id"])
    positions = handlers["list_paper_positions"]()
    monitor = handlers["monitor_paper_positions"]()
    learning = handlers["reflect_trades"]()
    backtest = handlers["run_backtest"](["BULL"], lookback=90, min_lookback=30, holding_period=5, step=10)

    assert regime["symbol"] == "BULL"
    assert ranked[0]["rank"] == 1
    assert ranked[0]["risk_status"] == "approved"
    assert proposal["proposal_id"]
    assert risk["approved"] is True
    assert readiness["ready"] is False
    assert "Set EXECUTION_MODE=live" in readiness["blockers"]
    assert result["status"] == "dry_run"
    assert execution["status"] == "dry_run"
    assert positions[0]["proposal_id"] == proposal["proposal_id"]
    assert monitor[0]["position_id"] == proposal["proposal_id"]
    assert learning["reflections"]
    assert backtest["trades"]


def test_agent_specs_include_required_roles() -> None:
    names = {spec.name for spec in build_agent_specs()}

    assert "Regime Detection Agent" in names
    assert "Options Strategy Agent" in names
    assert "Trade Ranking Agent" in names
    assert "Risk Agent" in names
    assert "Execution Agent" in names
    assert "Monitoring Agent" in names
    assert "Learning Reflection Agent" in names
