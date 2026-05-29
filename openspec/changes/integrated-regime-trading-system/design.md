## Context

This change introduces a new, production-oriented trading infrastructure stack for regime intelligence and defined-risk options workflows. The current workspace has no existing specs, so the design establishes the first set of module boundaries, data contracts, safety gates, and rollout expectations.

The source blueprint calls for a provider-agnostic market data foundation, Public.com as the initial broker/data integration, deterministic regime mathematics, an MCP tool surface, an Agno multi-agent workflow, real-time monitoring, and a learning loop. The domain is financially sensitive: the system must make every market-data transformation, regime classification, trade proposal, risk decision, and execution attempt inspectable and auditable.

## Goals / Non-Goals

**Goals:**

- Build a provider-agnostic market data layer with Public.com as the first adapter.
- Normalize equities, options, and available crypto data into typed schemas consumed by all downstream components.
- Implement a deterministic feature and regime engine for returns, volatility, Wasserstein distance, entropy, clustering, transition state, confidence, and key drivers.
- Convert regime output into options strategy proposals that include rationale, selected contracts, sizing, risk metrics, and alternatives.
- Require portfolio risk approval and Public.com multi-leg preflight before any live multi-leg order placement.
- Expose typed MCP tools and Agno agents that orchestrate deterministic modules without exposing arbitrary code execution, raw SQL, unrestricted HTTP, or secrets.
- Support real-time state, monitoring, audit logs, and post-trade learning from day one, even if advanced online clustering and production deployment arrive in later phases.

**Non-Goals:**

- Guaranteeing profit, win rate, or financial outcomes.
- Enabling live trading by default before credentials, risk limits, audit logging, and operator approval are configured.
- Building a general-purpose autonomous shell, Python, SQL, or web execution agent.
- Supporting every broker or data provider in the first implementation.
- Implementing advanced portfolio optimization, full historical backtesting, or self-modifying strategy deployment in the first pass.

## Decisions

### Decision: Use layered deterministic services beneath agents

Implement the system as explicit layers: data adapters, normalization, feature engine, regime engine, scanner, strategy engine, risk engine, execution adapter, monitoring, persistence, MCP tools, and Agno agents. Agents coordinate these services and explain decisions, but core regime detection, risk checks, and execution validation remain deterministic modules with typed inputs and outputs.

**Rationale:** This keeps financial decisions testable, repeatable, and auditable. It also prevents LLM reasoning from becoming the hidden source of truth for regime labels, risk calculations, or order placement.

**Alternatives considered:** A single autonomous agent with direct broker access would be faster to prototype but is not acceptable for safety or auditability. A notebook-first implementation would be useful for research but would not provide the stable contracts required for MCP tools and production monitoring.

### Decision: Start with Public.com behind a provider adapter

Create a `MarketDataProvider` and `BrokerExecutionProvider` abstraction, then implement Public.com as the first provider. Public-specific request and response details stay inside the adapter; downstream modules consume normalized schemas for bars, quotes, option chains, Greeks, accounts, positions, preflight results, and orders.

**Rationale:** The blueprint starts with Public.com, but the system requirement is provider-agnostic operation. Adapter boundaries allow later providers to be added without rewriting regime, strategy, or monitoring logic.

**Alternatives considered:** Calling Public.com SDK methods directly from every engine would reduce initial code but would spread provider assumptions across the system and make testing harder.

### Decision: Use typed schemas and immutable decision records

Define typed models for normalized market data, feature outputs, regime outputs, strategy proposals, risk decisions, execution requests, preflight results, execution results, monitoring snapshots, and learning reflections. Persist immutable records for every regime-to-decision-to-execution step.

**Rationale:** Typed schemas make MCP tool contracts stable and let tests validate behavior at module boundaries. Immutable decision records support replay, debugging, compliance review, and post-trade learning.

**Alternatives considered:** Passing raw dictionaries between modules is flexible but will allow schema drift. Inferring schemas from dataframes alone is convenient for research but weak for API and audit contracts.

### Decision: Keep mathematical regime detection isolated

Implement feature generation and regime classification outside the agent layer. The regime engine will compute log returns, rolling volatility, Wasserstein distances, entropy, momentum, options-derived features, clustering labels, transition probabilities, confidence, and key drivers. Human-readable labels are derived from classifier rules over computed features and cluster statistics.

**Rationale:** The regime label is the foundation for trade selection. It must be explainable from data, not guessed by a language model.

**Alternatives considered:** A rules-only regime detector is easier to ship but too brittle for the desired cross-asset regime intelligence. An LLM-only detector is not acceptable because it is non-deterministic and hard to validate.

### Decision: Gate execution through risk and preflight

Represent every trade as a `StrategyProposal` first. A `RiskDecision` must approve or reject it based on buying power, max loss, portfolio exposure, Greeks, symbol concentration, regime confidence, entropy, Wasserstein instability, and configured limits. The execution layer must then run provider preflight before placing any live order.

**Rationale:** Options trades can have nonlinear risk and operational failure modes. Separating proposal, risk approval, preflight, and placement gives the system clear denial points and audit records.

**Alternatives considered:** Letting the strategy agent place orders directly would reduce orchestration, but it removes the most important safety boundaries.

### Decision: Default to paper or dry-run execution

The system will ship with live trading disabled until an operator enables it through configuration, provides credentials, confirms account context, sets risk limits, and passes an execution readiness check. Dry-run mode records the same decision artifacts without submitting orders.

**Rationale:** This allows development, testing, and monitoring validation without accidental live trades.

**Alternatives considered:** Using live credentials during early development would test the true integration path but creates unnecessary operational risk.

### Decision: Expose a narrow MCP tool surface

Expose only validated tools such as `detect_regime`, `compare_regimes`, `scan_market`, `propose_options_strategy`, `check_portfolio_risk`, `execute_trade`, `get_live_monitoring`, `retrain_clusters`, and `reflect_on_trade`. Each tool accepts structured inputs and returns deterministic JSON.

**Rationale:** MCP is the AI-native entry point, so it needs strong contracts and clear authorization boundaries. A narrow tool surface is easier to test and secure.

**Alternatives considered:** Exposing generic database, HTTP, shell, or Python tools would be flexible but unsafe and inconsistent with production trading controls.

### Decision: Use event-driven streaming with durable state

Use a WebSocket ingestion path to update rolling feature windows, recompute lightweight regime state, publish events, and update live monitoring. Redis stores latest live state and rolling windows, Parquet stores historical bars and feature snapshots, and PostgreSQL stores account metadata, trade journal entries, learned heuristics, audit records, and execution records.

**Rationale:** Real-time monitoring needs low-latency state while learning and audit workflows need durable records. Splitting live state from historical and relational records keeps each storage layer focused.

**Alternatives considered:** Storing everything in PostgreSQL simplifies operations but is less suitable for rolling windows and high-frequency updates. Storing everything in Redis is fast but not durable enough for audit and learning.

## Risks / Trade-offs

- Public.com API or SDK behavior changes -> Keep provider calls isolated in adapters, pin SDK versions, add contract tests, and include readiness checks against sandbox or dry-run account paths where available.
- Live trading causes unintended orders -> Default to dry-run mode, require explicit live enablement, risk approval, preflight, idempotency keys, operator-visible audit logs, and kill-switch configuration.
- Regime model overfits historical data -> Separate training and evaluation, log feature distributions, backtest by time period, require confidence thresholds, and monitor performance by regime after deployment.
- Wasserstein and clustering computations are expensive during streaming -> Maintain rolling feature windows, use lightweight incremental recomputation for live updates, and schedule heavier retraining outside the critical path.
- Option chain data is incomplete or stale -> Include quote timestamps, liquidity filters, spread checks, max age limits, and rejection reasons in strategy proposals.
- Agent output drifts from deterministic contracts -> Agents must call typed services and return their structured outputs; tests validate tool schemas and forbid arbitrary execution surfaces.
- Persistence stack increases operational complexity -> Start with local Docker services and explicit migrations; allow the first dry-run path to operate with reduced persistence only for development.
- Financial compliance and user suitability constraints are unclear -> Keep the product as user-controlled tooling, require explicit operator configuration, log all decisions, and leave compliance/legal requirements as a launch-blocking open question.

## Migration Plan

1. Create foundational packages and configuration for providers, schemas, persistence, and feature/regime services.
2. Implement the Public.com adapter in dry-run-safe mode and verify account, quotes, bars, option chains, positions, and preflight read paths before any placement path is enabled.
3. Implement feature and regime engines with offline historical data tests, then expose `detect_regime` and `scan_market` through MCP.
4. Add the strategy, risk, and execution workflow with dry-run execution records and preflight-only validation.
5. Add streaming ingestion, live monitoring state, audit persistence, and basic dashboards.
6. Add Agno agents as orchestrators over the typed services.
7. Add post-trade learning, retraining triggers, and performance-by-regime reporting.
8. Enable live trading only after explicit operator configuration, readiness checks, kill-switch validation, and a successful paper/dry-run burn-in.

Rollback is service-oriented: disable live execution first, then disable agent-driven execution, then disable streaming updates while preserving historical data and audit records. Provider adapters and MCP tools should fail closed when configuration, credentials, schema validation, or risk checks fail.

## Open Questions

- Which runtime stack should host the initial implementation: a pure Python service, a mixed Python and TypeScript service, or an existing application framework?
- Does Public.com provide a paper-trading or sandbox path for the account type being used, or must dry-run mode be implemented entirely in the application?
- What exact account-level risk limits should be defaults for max loss, max position size, max portfolio delta, max open trades, and symbol concentration?
- Which instruments are in scope for launch: equities and equity/ETF options only, or crypto data and trading as well?
- What operator approval model is required before live execution: manual confirmation per order, allowlisted strategy classes, or fully automated within strict limits?
