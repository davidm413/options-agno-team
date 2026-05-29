## Why

The project needs production-grade infrastructure that turns market data into auditable regime intelligence and bounded options trade decisions, rather than a notebook, static scanner, or rule-only bot. Building this now creates a provider-agnostic foundation for real-time Public.com trading while keeping the mathematical regime engine, agent orchestration, and execution controls explicit and testable.

## What Changes

- Add a provider-agnostic market data layer with an initial Public.com adapter for equities, options, and available crypto data.
- Add a mathematical feature and regime intelligence engine that produces deterministic regime labels, confidence scores, directional bias, and key drivers from normalized market data.
- Add a market scanner that evaluates configured symbols and ranks regime opportunities and anomalies across assets.
- Add an options strategy workflow that converts regime output into defined-risk trade proposals, portfolio risk decisions, preflight checks, and execution requests.
- Add an MCP and Agno orchestration layer that exposes validated typed tools and coordinates specialist agents for detection, strategy, risk, execution, monitoring, and learning.
- Add streaming state, persistence, audit logging, monitoring, and feedback loops for real-time updates and post-trade learning.
- Add safety guardrails that require deterministic tool inputs, paper/dry-run operation by default, preflight validation before execution, and risk approval before order placement.

## Capabilities

### New Capabilities

- `market-data-ingestion`: Provider abstraction, Public.com adapter, normalized market and options schemas, retries, rate limits, caching, and streaming inputs.
- `regime-intelligence-engine`: Feature generation, Wasserstein and entropy metrics, clustering, regime classification, hidden-state transitions, confidence, and key drivers.
- `market-scanner`: Configurable universe scanning, cross-asset comparisons, anomaly detection, and ranked regime summaries.
- `options-trading-workflow`: Strategy proposal, option-chain selection, portfolio risk review, preflight validation, execution requests, live monitoring, and roll/close recommendations.
- `agent-mcp-orchestration`: Typed MCP tools and Agno agents that coordinate market data, regime detection, strategy, risk, execution, monitoring, and learning without exposing arbitrary execution.
- `streaming-state-persistence`: Redis-backed live state, Parquet historical features, PostgreSQL trade journal and metadata, event bus updates, metrics, and audit trails.
- `learning-feedback-loop`: Post-trade reflection, performance-by-regime analytics, learned heuristics, retraining triggers, and parameter improvement recommendations.

### Modified Capabilities

None.

## Impact

- Affected code areas will include new data adapters, feature and regime engines, scanner services, options strategy and risk modules, MCP server tools, Agno agent workflows, streaming workers, persistence models, and deployment configuration.
- New runtime dependencies are expected for the Public.com Python SDK, numerical feature computation, clustering and distance metrics, MCP serving, Agno agent orchestration, Redis, PostgreSQL, Parquet storage, and observability.
- External systems include Public.com REST and WebSocket APIs, account authentication, market data streams, options chain and Greeks data, multi-leg preflight, and multi-leg order placement.
- Operational impact includes strict audit logging, paper/dry-run mode, risk limits, secrets management, monitoring dashboards, and explicit controls around any live trading action.
