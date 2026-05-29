# Regime Trader

Regime Trader is a Python service scaffold for deterministic market regime intelligence and
paper-first options workflows. The system keeps market math, risk checks, execution gates, MCP
tools, and agent handoffs typed and auditable.

## Development

```powershell
uv sync --extra dev
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest
uv run regime-trader readiness --config config/sample.yaml
```

Live trading is disabled by default. Any live placement path requires explicit configuration,
risk approval, provider preflight, an idempotency key, and a kill-switch check.
