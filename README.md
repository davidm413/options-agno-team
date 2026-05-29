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

## CLI Vertical Slice

The CLI uses SQLite audit storage by default at `.options_agno_team/audit.sqlite3`.
Override it with `--db path\to\audit.sqlite3` or `AUDIT_DB_PATH`.

```powershell
$env:PYTHONPATH="src"
python -m options_agno_team.cli detect-regime SPY
python -m options_agno_team.cli propose-strategy SPY
python -m options_agno_team.cli rank-candidates SPY QQQ NVDA
python -m options_agno_team.cli check-risk <proposal_id>
python -m options_agno_team.cli live-readiness
python -m options_agno_team.cli preflight <proposal_id>
python -m options_agno_team.cli execute <proposal_id>
python -m options_agno_team.cli paper-positions
python -m options_agno_team.cli mark-to-market
python -m options_agno_team.cli backtest SPY QQQ --lookback 180 --min-lookback 60 --holding-period 10
python -m options_agno_team.cli monitor-once
python -m options_agno_team.cli monitor-loop --iterations 3 --interval-seconds 60
python -m options_agno_team.cli reflect-trades
```

When installed as a package, the same commands are available through `options-agno`.
Dry-run executions create simulated paper positions; `mark-to-market` refreshes spread marks and
basic unrealized P&L from the current adapter quotes.

## Backtesting, Monitoring, and Learning

`backtest` replays historical bars through feature generation, regime classification, strategy
selection, risk checks, and simulated outcomes. Reports include win rate, max drawdown, average
return, regime accuracy, and performance grouped by strategy and symbol.

`monitor-once` refreshes open paper positions and detects exit triggers:

- profit target
- stop loss
- time decay
- max days in trade
- regime flip
- delta drift
- high entropy spike

`reflect-trades` records the original proposal rationale, compares current regime to the original
thesis, and groups results by strategy/volatility/bias/symbol. Reports include sentences such as
`bull call spreads in medium-vol bullish regimes on NVDA performed poorly` with supporting win-rate,
average-P&L, and thesis-match statistics.

The SQLite audit DB now records backtest reports, monitoring events, and trade reflections.

## Public.com Smoke Checks

Live Public.com smoke checks are opt-in and never run during normal tests. They call bars, quotes,
option expirations, option chains, greeks, account, positions, and spread preflight.

Public preflight can be tested without order placement:

```powershell
$env:PYTHONPATH="src"
$env:PUBLIC_SMOKE_ENABLED="true"
$env:DATA_MODE="public"
$env:EXECUTION_MODE="dry_run"
$env:API_SECRET_KEY="..."
$env:DEFAULT_ACCOUNT_NUMBER="..."
python -m options_agno_team.cli public-smoke SPY
```

Live-mode smoke preflight additionally requires live gates:

```powershell
$env:PYTHONPATH="src"
$env:PUBLIC_SMOKE_ENABLED="true"
$env:DATA_MODE="public"
$env:EXECUTION_MODE="live"
$env:ENABLE_LIVE_TRADING="true"
$env:LIVE_CONFIRMATION="CONFIRM LIVE OPTIONS TRADING"
$env:LIVE_RISK_LIMITS_CONFIRMED="true"
$env:LIVE_ALERTING_CONFIRMED="true"
$env:ALERT_WEBHOOK_URL="https://example.invalid/options-alerts"
$env:API_SECRET_KEY="..."
$env:DEFAULT_ACCOUNT_NUMBER="..."
python -m options_agno_team.cli public-smoke SPY
```

`EXECUTION_MODE=dry_run` can call real Public preflight in `DATA_MODE=public`, but `execute` still
does not place orders. The Public adapter client is reused by the execution gateway so dry-run
preflight reaches the broker preflight endpoint without enabling live order placement.

## MCP

```powershell
$env:PYTHONPATH="src"
python -m options_agno_team.cli serve-mcp
```

## Agno AgentOS

AgentOS is optional and uses an open-source Ollama model by default.

```powershell
python -m pip install -e ".[agno]"
ollama pull llama3.1:8b
$env:PYTHONPATH="src"
$env:AGNO_MODEL_ID="llama3.1:8b"
python -m options_agno_team.cli serve-agent-os
```

The server defaults to `http://localhost:7777`, persists AgentOS sessions in
`.options_agno_team/agno_os.sqlite3`, and exposes the team as `options-trading-team`.
AgentOS MCP is enabled by default at `/mcp`; pass `--no-mcp` to disable it.

Useful overrides:

```powershell
$env:AGNO_MODEL_ID="qwen2.5:7b"
$env:AGNO_OLLAMA_HOST="http://localhost:11434"
$env:AGNO_OS_DB_PATH=".options_agno_team/agentos.sqlite3"
python -m options_agno_team.cli serve-agent-os --port 7777
```

## Main Components

- Fixture and Public.com market data adapters
- Deterministic feature, regime, strategy, risk, and execution services
- SQLite audit storage and paper-trading state
- Trader-grade option selection filters for DTE, delta, spread width, liquidity, bid/ask width,
  IV rank, volume, and open interest
- Backtesting, monitoring, and learning/reflection services
- FastMCP tool registration helpers
- Agno agent/team factory helpers
- Agno AgentOS runtime using an open-source Ollama model by default
- Deterministic candidate ranking for MCP and Agno workflows

## Live Trading Gates

Live placement remains gated by:

- `EXECUTION_MODE=live`
- `ENABLE_LIVE_TRADING=true`
- `LIVE_CONFIRMATION="CONFIRM LIVE OPTIONS TRADING"`
- `LIVE_RISK_LIMITS_CONFIRMED=true`
- `LIVE_ALERTING_CONFIRMED=true`
- `ALERT_WEBHOOK_URL` or `ALERT_STDOUT_ENABLED=true`
- deterministic risk approval
- Public preflight
- kill switch disabled
- daily loss, max open trades, and max trades per day limits

Run `python -m options_agno_team.cli live-readiness` before setting live mode. It returns each
gate, the explicit confirmations present, configured risk limits, alerting status, and blockers.
Live execution and live-mode Public smoke checks reject until the readiness report is clean.
