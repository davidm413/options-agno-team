# AGENTS.md

## Scope
These instructions apply to the entire repository. User prompts override this file. If nested `AGENTS.md` files are added later, the closest file to the changed code takes precedence.

## Project Mission
Build an AI-native, mathematically rigorous market regime intelligence and options trading system. The system combines deterministic regime detection, options strategy selection, risk review, execution preflight, real-time monitoring, and a learning loop exposed through typed MCP tools and Agno agents.

## Source Of Truth
- Primary blueprint: `Integrated_Regime_Trading_System_Blueprint.md`.
- If the blueprint is not versioned in this repo yet, ask before making major architecture decisions and prefer adding it under `docs/`.
- OpenSpec is enabled with `schema: spec-driven`; use it for non-trivial feature work.

## Source Code Reference
Source code for dependencies and external repositories is cached at `~/.opensrc/`.

### Available Codebases
The following source code is available for analysis and reference:

- **publicdotcom-py**: Public.com Python SDK
- **python-sdk**: Model Context Protocol Python SDK
- **mirkovicdev/CLUSTERING-MARKET-REGIMES**: Clustering and market regime analysis
- **agno-agi/agno**: AI agent framework
- **agno**: Additional agno components

### Setup
Pre-fetch all source code into the cache:

```bash
opensrc fetch publicdotcom-py python-sdk mirkovicdev/CLUSTERING-MARKET-REGIMES agno-agi/agno agno
```

### Usage Examples

#### Search in specific codebases

```bash
# Search Public.com SDK
rg "market|trade|order" $(opensrc path publicdotcom-py)

# Search Model Context Protocol SDK
grep -r "protocol|message" $(opensrc path python-sdk)

# Search clustering and market regimes
rg "cluster|regime|volatility" $(opensrc path mirkovicdev/CLUSTERING-MARKET-REGIMES)

# Search agno AI agent framework
grep -r "Agent|execute|task" $(opensrc path agno-agi/agno)
rg "behavior|action" $(opensrc path agno)
```

#### Read specific files

```bash
# Explore structure
cat $(opensrc path publicdotcom-py)/README.md
cat $(opensrc path python-sdk)/README.md
cat $(opensrc path mirkovicdev/CLUSTERING-MARKET-REGIMES)/README.md
cat $(opensrc path agno-agi/agno)/src/core.py

# Find implementation details
find $(opensrc path publicdotcom-py) -name "*.py" -type f
find $(opensrc path python-sdk) -name "*.py" -type f
```

### Integration Patterns
When integrating these systems together:

```bash
# Find how Public.com SDK handles data
grep -r "class.*Client|def.*get" $(opensrc path publicdotcom-py)

# Find protocol message handling
grep -r "class.*Message|def.*handle" $(opensrc path python-sdk)

# Find clustering algorithms
grep -r "def.*cluster|class.*Cluster" $(opensrc path mirkovicdev/CLUSTERING-MARKET-REGIMES)

# Find agent task execution
grep -r "def.*execute|class.*Task" $(opensrc path agno-agi/agno)
```

### Cross-codebase analysis

```bash
# Find all data models across systems
find $(opensrc path publicdotcom-py) $(opensrc path python-sdk) -name "*model*.py"

# Search for common patterns
rg "async def|@property" $(opensrc path publicdotcom-py) $(opensrc path agno-agi/agno)

# Compare implementations
grep -h "def __init__" $(opensrc path publicdotcom-py)/src/*.py $(opensrc path python-sdk)/src/*.py
```

### Individual Paths
If you need direct access to any codebase:

```bash
PUBLIC_DOT_COM=$(opensrc path publicdotcom-py)
MCP_SDK=$(opensrc path python-sdk)
CLUSTERING=$(opensrc path mirkovicdev/CLUSTERING-MARKET-REGIMES)
AGNO_AGI=$(opensrc path agno-agi/agno)
AGNO=$(opensrc path agno)

# Use in scripts
ls -la "$PUBLIC_DOT_COM/src/"
cat "$MCP_SDK/README.md"
```

All source code is automatically cached at `~/.opensrc/` on first use.

When running these examples on Windows, adapt Bash command substitution and environment variable syntax to PowerShell as needed.

## Non-Negotiables
- Do not implement live order placement without paper-trading defaults, explicit human approval, and preflight risk checks.
- Never commit secrets, API tokens, account IDs, credentials, or private trading data.
- Keep core math deterministic. LLMs may orchestrate, explain, or call tools, but must not guess regime/risk outputs.
- MCP and Agno tools must expose typed, validated JSON interfaces only.
- Do not expose arbitrary shell execution, arbitrary Python execution, unrestricted SQL, unrestricted HTTP, or raw internal model state through tools.
- Keep Public.com behind provider adapters so the system can swap providers later.

## Architecture Direction
Use a Python `src/` layout unless the repo later establishes a different convention.

Suggested module boundaries:

- `data/`: provider adapters, Public.com SDK wrapper, WebSocket client, normalization, retry/rate-limit logic.
- `engine/`: returns, volatility, distributions, Wasserstein distance, entropy, feature vector construction.
- `regimes/`: clustering, hidden-state transitions, classification, regime confidence, key drivers.
- `strategy/`: options strategy mapping, strike/expiration selection, proposal generation.
- `risk/`: portfolio limits, Greeks checks, buying power, max loss, correlation, approval/rejection.
- `execution/`: preflight and order placement boundaries; live execution disabled by default.
- `mcp/`: FastMCP server and typed tool registrations.
- `agents/`: Agno market data, regime, strategy, risk, execution, monitoring, and learning agents.
- `storage/`: Redis cache, Parquet history, PostgreSQL trade journal and learned rules.
- `config/`: symbols, risk limits, feature flags, strategy settings, streaming thresholds.

## Build Order
1. Public.com adapter, normalized market/options schema, and offline fixtures.
2. Feature engine: log returns, realized volatility, Wasserstein distance, entropy, momentum, options IV features.
3. Basic regime engine with clustering, labels, confidence, and transition probabilities.
4. MCP tools: `detect_regime`, `scan_market`, `compare_regimes`.
5. Strategy and risk engines with paper-only execution boundaries.
6. Agno agent team and monitoring loop.
7. Learning/reflection, backtesting, production hardening, observability.

## Engineering Workflow
- Read the blueprint and relevant OpenSpec artifacts before implementing.
- For substantial changes, create or continue an OpenSpec change before coding.
- Keep changes scoped to the active task. Do not refactor unrelated areas.
- Preserve user edits and untracked files unless explicitly asked to change them.
- Prefer small, typed, testable modules over notebook-style scripts.
- Update docs and OpenSpec tasks when behavior or architecture changes.

## Python Standards
- Use `pyproject.toml` for tooling once the project is scaffolded.
- Prefer Python 3.11+.
- Use type hints throughout public interfaces.
- Use Pydantic models or dataclasses for API/tool schemas.
- Use `Decimal` for money/accounting boundaries; floats are acceptable inside statistical calculations where appropriate.
- Use timezone-aware UTC timestamps for market data and events.
- Avoid hard-coded symbols, regimes, strategies, risk limits, and API endpoints outside configuration.

## Testing And Validation
When tooling exists, run the relevant subset before finishing:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest
```

Testing expectations:

- Unit-test math, schema validation, risk checks, and strategy mapping.
- Mock Public.com and broker/network calls in normal tests.
- Put live/API integration tests behind explicit opt-in markers.
- Backtests must avoid look-ahead bias and separate training, validation, and evaluation periods.

## Trading Safety
- Default to paper trading.
- Require `preflight_multileg` before any multi-leg order placement.
- Reject strategies without defined max loss unless explicitly enabled by config and approved by the user.
- Risk sizing must come from config and portfolio state, not hard-coded constants.
- Log every regime, signal, risk decision, preflight result, order attempt, and post-trade outcome.
- Do not present system outputs as financial advice.

## MCP And Agent Rules
- FastMCP tools should use explicit typed parameters and JSON-serializable return values.
- Agno agents should use structured outputs for regime, strategy, risk, execution, monitoring, and learning records.
- Agents coordinate workflow; deterministic engines own calculations and decisions.
- Tool outputs should include confidence, assumptions, and rejection reasons where relevant.
- Monitoring and learning agents may propose actions, but execution remains gated by risk and approval controls.

## Done Criteria
A task is done only when:

- The change is implemented in the correct layer.
- Relevant tests or documented manual checks pass.
- Public interfaces are typed and documented.
- Security and trading guardrails still hold.
- OpenSpec tasks/docs are updated when applicable.
