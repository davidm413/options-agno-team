## ADDED Requirements

### Requirement: Live state cache
The system SHALL maintain live market, feature, regime, position, and monitoring state in a low-latency cache with explicit freshness metadata.

#### Scenario: Latest regime lookup
- **WHEN** a caller requests live monitoring for a subscribed symbol
- **THEN** the system SHALL return the latest cached regime, feature summary, position status, and freshness timestamps

#### Scenario: Cache entry expires
- **WHEN** cached live state exceeds configured freshness limits
- **THEN** the system SHALL mark the state stale and SHALL NOT present it as current

### Requirement: Durable historical feature storage
The system SHALL persist historical bars, normalized market snapshots, and feature snapshots to time-series-friendly storage for replay, training, and audit.

#### Scenario: Persist feature snapshot
- **WHEN** the feature engine computes a feature vector for a symbol and timestamp
- **THEN** the system SHALL store the feature snapshot with feature names, values, input data reference, and feature configuration version

#### Scenario: Replay historical decision
- **WHEN** an operator requests replay of a historical regime decision
- **THEN** the system SHALL load the relevant historical data and feature snapshots needed to reproduce the decision path

### Requirement: Relational trade and audit records
The system SHALL store trade journal entries, strategy proposals, risk decisions, preflight responses, execution records, monitoring alerts, learned heuristics, and audit events in relational storage.

#### Scenario: Record complete decision chain
- **WHEN** a trade candidate proceeds from regime output to strategy proposal to risk decision to preflight
- **THEN** the system SHALL persist linked records that identify each step and its status

#### Scenario: Execution denied
- **WHEN** execution is denied by authorization, risk, preflight, configuration, or provider response
- **THEN** the system SHALL persist the denial reason and link it to the attempted workflow

### Requirement: Event bus for real-time updates
The system SHALL publish normalized events for market data updates, feature changes, regime changes, scan results, alerts, risk breaches, and execution status changes.

#### Scenario: Regime shift event
- **WHEN** the regime engine detects a regime change that crosses configured thresholds
- **THEN** the system SHALL publish a regime shift event with symbol, previous state, new state, confidence, key drivers, and timestamp

#### Scenario: Monitoring consumes events
- **WHEN** a monitoring workflow subscribes to regime and market events
- **THEN** it SHALL update live position state and alert status without polling provider APIs unnecessarily

### Requirement: Metrics and observability
The system SHALL expose operational metrics, structured logs, and health checks for provider connectivity, streaming state, feature latency, regime updates, scan jobs, MCP tools, agent workflows, and execution gates.

#### Scenario: Provider health degrades
- **WHEN** provider requests or streaming connections fail above configured thresholds
- **THEN** the system SHALL emit health status, logs, and metrics that identify the affected provider and operation type

#### Scenario: Execution workflow observed
- **WHEN** an execution workflow runs in dry-run or live mode
- **THEN** the system SHALL emit metrics for proposal, risk, preflight, placement, and final status without logging secrets

### Requirement: Configuration versioning
The system SHALL version runtime configuration that affects symbols, features, models, strategy mapping, risk limits, streaming thresholds, and execution mode.

#### Scenario: Risk limit changes
- **WHEN** an operator changes risk configuration
- **THEN** new decisions SHALL reference the new configuration version while historical decisions retain their original configuration reference
