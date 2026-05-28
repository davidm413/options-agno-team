from options_agno_team.config import AppConfig, DataMode, ExecutionMode


def test_config_defaults_to_fixture_dry_run() -> None:
    config = AppConfig.from_env({})

    assert config.data_mode is DataMode.FIXTURE
    assert config.execution_mode is ExecutionMode.DRY_RUN
    assert config.enable_live_trading is False
    assert config.live_order_enabled is False


def test_live_order_enabled_requires_both_flags() -> None:
    config = AppConfig.from_env({"EXECUTION_MODE": "live", "ENABLE_LIVE_TRADING": "true"})

    assert config.execution_mode is ExecutionMode.LIVE
    assert config.live_order_enabled is True
