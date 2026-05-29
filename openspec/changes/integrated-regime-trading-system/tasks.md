## 1. Project Foundation

- [x] 1.1 Initialize a Python service package with modules for data, schemas, features, regimes, scanner, trading, agents, MCP, persistence, config, observability, and tests
- [x] 1.2 Add dependency management for Public.com SDK access, typed models, numerical computing, clustering, Redis, PostgreSQL, Parquet, MCP serving, Agno agents, and testing
- [x] 1.3 Define application configuration models for providers, symbols, features, regimes, strategies, risk limits, streaming, persistence, and execution mode
- [x] 1.4 Implement secret loading and redaction utilities for provider credentials, account identifiers, and sensitive configuration
- [x] 1.5 Add a test fixture suite with deterministic market data, option chains, provider mocks, and sample regime scenarios
- [x] 1.6 Add developer commands for linting, formatting, type checking, unit tests, and local service startup

## 2. Market Data Ingestion

- [x] 2.1 Define provider-neutral interfaces for bars, quotes, option expirations, option chains, Greeks, account data, positions, preflight, and order placement boundaries
- [x] 2.2 Implement typed normalized schemas for OHLCV bars, quotes, option contracts, option chains, Greeks, accounts, positions, and provider metadata
- [x] 2.3 Implement Public.com adapter authentication, account lookup, quotes, bars, option expirations, option chains, Greeks where available, and positions
- [x] 2.4 Add market data validation for freshness, timestamp ordering, missing intervals, required fields, and stale options data
- [x] 2.5 Implement retry, timeout, rate-limit, and cache-aware fallback behavior for provider reads
- [x] 2.6 Implement WebSocket ingestion for available Public.com streams and normalize streaming quote, bar, and option update events
- [x] 2.7 Add provider adapter contract tests with mocked Public.com responses and failure cases
- [x] 2.8 Add streaming interruption tests for reconnect, gap detection, backfill request, and stream health events

## 3. Feature And Regime Engine

- [x] 3.1 Implement feature functions for log returns, rolling realized volatility, momentum, Wasserstein distance, and entropy
- [x] 3.2 Implement options-derived feature functions for implied volatility rank, skew, term structure slope, and strength metrics
- [x] 3.3 Implement the master feature vector builder with feature names, values, input window references, and configuration version metadata
- [x] 3.4 Implement weighted clustering or Gaussian mixture regime assignment with deterministic model versioning
- [x] 3.5 Implement classifier rules that map cluster statistics and feature values to volatility regime, directional bias, regime label, confidence, and key drivers
- [x] 3.6 Implement transition state modeling for regime persistence and transition probabilities
- [x] 3.7 Implement lightweight online updates for streaming feature and regime refreshes
- [x] 3.8 Implement explicit cluster retraining with candidate model metadata and rollback reference
- [x] 3.9 Add unit tests for feature calculations, regime classification, insufficient confidence, transition history gaps, and reproducibility metadata

## 4. Streaming State And Persistence

- [x] 4.1 Add Redis-backed live state repositories for latest market data, features, regimes, positions, and monitoring snapshots
- [x] 4.2 Add Parquet storage for historical bars, normalized market snapshots, and feature snapshots
- [x] 4.3 Add PostgreSQL models and migrations for trade journal entries, strategy proposals, risk decisions, preflight responses, execution records, monitoring alerts, learned heuristics, model metadata, and audit events
- [x] 4.4 Implement event bus messages for market updates, feature updates, regime shifts, scan results, risk breaches, execution status, and learning events
- [x] 4.5 Implement configuration version persistence and reference configuration versions from every decision record
- [x] 4.6 Add structured logging, metrics, and health checks for provider connectivity, stream health, feature latency, regime updates, MCP tools, agents, and execution gates
- [x] 4.7 Add persistence tests for linked decision chains, stale live state, historical replay references, and secret redaction in logs

## 5. Market Scanner

- [x] 5.1 Implement configured scan universe loading for equities, options, and available crypto symbols
- [x] 5.2 Implement on-demand scans for explicit symbol lists and asset classes
- [x] 5.3 Implement per-symbol scan execution through data retrieval, feature generation, regime classification, and data quality evaluation
- [x] 5.4 Implement scan ranking using configured opportunity, confidence, risk, liquidity, and anomaly criteria
- [x] 5.5 Implement anomaly detection for Wasserstein spikes, entropy jumps, volatility shifts, and degraded data
- [x] 5.6 Implement scan fault isolation so provider or feature failures produce per-symbol errors without failing healthy symbols
- [x] 5.7 Add scheduled scan support for pre-market, intraday, and end-of-day workflows
- [x] 5.8 Add scanner tests for configured scans, explicit scans, mixed-asset summaries, anomaly flags, ranking, and partial failures

## 6. Options Trading Workflow

- [x] 6.1 Implement strategy mapping from regime label, volatility regime, directional bias, confidence, Wasserstein, entropy, and configuration to primary and alternative strategy types
- [x] 6.2 Implement option contract selection using expiration, strike, liquidity, bid-ask spread, delta, implied volatility, and max-loss filters
- [x] 6.3 Implement strategy proposal records with rationale, selected legs, pricing assumptions, exposure, max loss, max gain where calculable, and rejection criteria
- [x] 6.4 Implement portfolio risk review for buying power, max loss, portfolio delta, Greeks, concentration, correlation, open-trade limits, and required data completeness
- [x] 6.5 Implement dry-run execution records that preserve the full proposal, risk, and preflight decision path without placing orders
- [x] 6.6 Implement Public.com multi-leg preflight integration and persist estimated cost, buying power requirement, commission where available, strategy name, and validation result
- [x] 6.7 Implement live order placement behind explicit live-trading configuration, risk approval, successful preflight, idempotency keys, and kill-switch checks
- [x] 6.8 Implement position monitoring rules for regime thesis drift, P&L, Greeks, expiration, risk breaches, and hold, close, roll, or hedge recommendations
- [x] 6.9 Add workflow tests for strategy selection, no-contract rejection, risk approval and rejection, preflight rejection, dry-run behavior, live gate denial, and monitoring alerts

## 7. MCP And Agno Orchestration

- [x] 7.1 Implement typed MCP input and output schemas for `detect_regime`, `compare_regimes`, `scan_market`, `propose_options_strategy`, `check_portfolio_risk`, `execute_trade`, `get_live_monitoring`, `retrain_clusters`, and `reflect_on_trade`
- [x] 7.2 Implement MCP tool handlers that validate input, call deterministic services, return typed JSON, and record audit events
- [x] 7.3 Add authorization policies for account data, preflight, execution, retraining, and memory mutation tools
- [x] 7.4 Add deny-path handling for arbitrary shell, Python, SQL, unrestricted HTTP, raw credentials, and unvalidated order placement requests
- [x] 7.5 Implement Agno agents for regime detection, options strategy, risk and portfolio review, execution, monitoring, and learning
- [x] 7.6 Implement structured agent handoffs so each agent consumes and returns typed service outputs instead of free-form hidden state
- [x] 7.7 Implement approved shared memory reads for trade summaries, open positions, learned heuristics, and performance-by-regime metrics
- [x] 7.8 Add MCP and agent integration tests for valid workflows, invalid inputs, authorization failures, denied arbitrary execution, and unapproved execution rejection

## 8. Learning Feedback Loop

- [x] 8.1 Implement trade journal creation and updates for dry-run and live workflows
- [x] 8.2 Implement post-trade reflection that compares closed or expired trades against entry regime, thesis, strategy selection, risk assumptions, monitoring events, and outcome
- [x] 8.3 Implement incomplete-reflection handling that records missing market, outcome, or context data without inventing conclusions
- [x] 8.4 Implement performance-by-regime analytics grouped by symbol, regime label, directional bias, volatility regime, strategy type, confidence band, and time period
- [x] 8.5 Implement low-sample confidence labeling for performance metrics
- [x] 8.6 Implement learned heuristic records with evidence, provenance, affected regimes, proposed configuration change, and approval status
- [x] 8.7 Ensure unapproved learned heuristics cannot alter production strategy or risk behavior
- [x] 8.8 Implement retraining triggers for data drift, performance drift, stale model age, and authorized operator request
- [x] 8.9 Add learning tests for journal capture, reflection outcomes, low-sample analytics, heuristic approval gates, and retraining recommendations

## 9. Deployment And Safety Readiness

- [x] 9.1 Add Docker and local development configuration for the service, Redis, PostgreSQL, and any required workers
- [x] 9.2 Add sample configuration files for symbols, features, regimes, strategy mapping, risk limits, streaming thresholds, and dry-run execution
- [x] 9.3 Implement startup readiness checks for provider credentials, account context, persistence, event bus, live-trading disabled default, and kill-switch state
- [x] 9.4 Add an end-to-end dry-run workflow that ingests sample data, detects regime, scans market, proposes a strategy, reviews risk, runs preflight where configured, and records the decision chain
- [x] 9.5 Add an operator checklist for enabling live trading with risk limits, account confirmation, audit logging, preflight validation, and rollback steps
- [x] 9.6 Add documentation for MCP tools, agent roles, configuration, dry-run workflows, persistence layout, monitoring, and safety boundaries
- [x] 9.7 Run the full test suite and archive the verification output with the change before implementation is considered complete
