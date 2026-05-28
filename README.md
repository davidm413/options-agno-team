# Options Agno Team

Greenfield Python implementation of an AI-native market regime and options strategy system.

The default runtime is safe for local development:

- `DATA_MODE=fixture`
- `EXECUTION_MODE=dry_run`
- `ENABLE_LIVE_TRADING=false`

Live Public.com order placement is available only through the gated execution path after deterministic risk approval and Public preflight.

## Quick Start

```powershell
python -m pytest
```

## Main Components

- Fixture and Public.com market data adapters
- Deterministic feature, regime, strategy, risk, and execution services
- FastMCP tool registration helpers
- Agno agent/team factory helpers
