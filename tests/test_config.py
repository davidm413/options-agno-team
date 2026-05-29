from options_agno_team.config import AppConfig, DataMode, ExecutionMode
from options_agno_team.readiness import evaluate_live_readiness


def test_config_defaults_to_fixture_dry_run() -> None:
    config = AppConfig.from_env({})

    assert config.data_mode is DataMode.FIXTURE
    assert config.execution_mode is ExecutionMode.DRY_RUN
    assert config.enable_live_trading is False
    assert config.live_order_enabled is False


def test_live_order_enabled_requires_both_flags() -> None:
    config = AppConfig.from_env({"EXECUTION_MODE": "live", "ENABLE_LIVE_TRADING": "true"})

    assert config.execution_mode is ExecutionMode.LIVE
    assert config.live_order_enabled is False


def test_live_readiness_requires_explicit_confirmations_and_alerting() -> None:
    config = AppConfig.from_env(
        {
            "EXECUTION_MODE": "live",
            "ENABLE_LIVE_TRADING": "true",
            "LIVE_CONFIRMATION": AppConfig.live_confirmation_required,
            "LIVE_RISK_LIMITS_CONFIRMED": "true",
            "LIVE_ALERTING_CONFIRMED": "true",
            "ALERT_STDOUT_ENABLED": "true",
        }
    )

    readiness = evaluate_live_readiness(config)

    assert readiness.ready is True
    assert config.live_order_enabled is True
    assert readiness.checks["risk_limits_confirmed"] is True
    assert readiness.checks["alerting_enabled"] is True


def test_live_readiness_reports_blockers_before_live_mode() -> None:
    readiness = evaluate_live_readiness(AppConfig())

    assert readiness.ready is False
    assert "Set EXECUTION_MODE=live" in readiness.blockers
