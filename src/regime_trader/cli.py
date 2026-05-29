from __future__ import annotations

import json
from pathlib import Path

import typer

from regime_trader.config.models import load_config
from regime_trader.observability.health import readiness_check

app = typer.Typer(help="Regime Trader developer and operator commands.")


@app.callback()
def callback() -> None:
    """Regime Trader command group."""


@app.command()
def readiness(config: Path | None = None) -> None:
    app_config = load_config(config)
    result = readiness_check(app_config)
    typer.echo(json.dumps(result.model_dump(mode="json"), indent=2, sort_keys=True))
    if result.status != "ready":
        raise typer.Exit(code=1)


def main() -> None:
    app()
