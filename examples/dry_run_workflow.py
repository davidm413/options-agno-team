from __future__ import annotations

from regime_trader.config.models import AppConfig
from regime_trader.service import DryRunWorkflow
from regime_trader.testing.fixtures import FixtureProvider, fixture_account


def main() -> None:
    config = AppConfig()
    provider = FixtureProvider(config)
    workflow = DryRunWorkflow(config=config, provider=provider)
    execution = workflow.run_symbol("SPY", account=fixture_account())
    print(execution.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
