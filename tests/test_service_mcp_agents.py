from options_agno_team.agents import build_agent_specs
from options_agno_team.mcp_server import build_tool_handlers
from options_agno_team.models import ExecutionStatus
from options_agno_team.service import build_system


def test_service_full_fixture_flow() -> None:
    system = build_system()

    proposal = system.propose_options_strategy("BULL")
    risk = system.check_portfolio_risk(proposal.proposal_id)
    result = system.execute_strategy(proposal.proposal_id)

    assert risk.approved is True
    assert result.status is ExecutionStatus.DRY_RUN


def test_mcp_tool_handlers_return_jsonable_payloads() -> None:
    system = build_system()
    handlers = build_tool_handlers(system)

    regime = handlers["detect_regime"]("BULL")
    proposal = handlers["propose_options_strategy"]("BULL")
    risk = handlers["check_portfolio_risk"](proposal["proposal_id"])
    result = handlers["preflight_strategy"](proposal["proposal_id"])

    assert regime["symbol"] == "BULL"
    assert proposal["proposal_id"]
    assert risk["approved"] is True
    assert result["status"] == "dry_run"


def test_agent_specs_include_required_roles() -> None:
    names = {spec.name for spec in build_agent_specs()}

    assert "Regime Detection Agent" in names
    assert "Options Strategy Agent" in names
    assert "Risk Agent" in names
    assert "Execution Agent" in names
    assert "Monitoring Agent" in names
    assert "Learning Reflection Agent" in names
