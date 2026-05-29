## ADDED Requirements

### Requirement: Trade journal capture
The system SHALL capture trade journal records containing entry regime, strategy thesis, selected contracts, risk decision, preflight result, execution mode, monitoring events, exit outcome, and realized P&L where available.

#### Scenario: Dry-run journal entry
- **WHEN** a dry-run trade workflow completes
- **THEN** the system SHALL create a journal entry with the simulated proposal, risk decision, preflight status where available, and dry-run execution status

#### Scenario: Live trade journal entry
- **WHEN** a live trade receives provider execution updates
- **THEN** the system SHALL update the journal with provider order ids, fills where available, position state, and linked audit records

### Requirement: Post-trade reflection
The system SHALL evaluate completed or expired trades against the original regime thesis, strategy selection, risk assumptions, monitoring events, and final outcome.

#### Scenario: Reflect on closed trade
- **WHEN** a trade is closed or reaches expiration
- **THEN** the learning workflow SHALL compare outcome against the entry thesis and produce structured observations, failure modes, and improvement candidates

#### Scenario: Incomplete data for reflection
- **WHEN** a completed trade lacks required outcome or market context data
- **THEN** the learning workflow SHALL record an incomplete reflection status and identify the missing data instead of inventing conclusions

### Requirement: Performance by regime analytics
The system SHALL aggregate performance by symbol, regime label, directional bias, volatility regime, strategy type, confidence band, and time period.

#### Scenario: Generate regime performance report
- **WHEN** enough completed trade records exist for a regime and strategy type
- **THEN** the system SHALL compute performance metrics such as win rate, average return, drawdown, average holding time, and risk-adjusted outcome metrics

#### Scenario: Insufficient sample size
- **WHEN** sample size is below the configured threshold
- **THEN** the system SHALL mark metrics as low-confidence and SHALL NOT promote them to strategy rules automatically

### Requirement: Learned heuristic records
The system SHALL store learned heuristics as versioned, provenance-linked recommendations that require explicit approval before changing production strategy or risk configuration.

#### Scenario: Suggest strategy adjustment
- **WHEN** reflection and performance analytics identify a repeated pattern
- **THEN** the learning workflow SHALL create a recommendation with evidence, affected regimes, proposed configuration change, and approval status

#### Scenario: Prevent unapproved production change
- **WHEN** a learned heuristic has not been approved
- **THEN** strategy and risk engines SHALL NOT apply it as production behavior

### Requirement: Retraining triggers
The system SHALL trigger or recommend feature, clustering, and classifier retraining when data drift, performance drift, stale model age, or operator request thresholds are met.

#### Scenario: Performance drift detected
- **WHEN** performance by regime degrades beyond configured thresholds
- **THEN** the learning workflow SHALL create a retraining recommendation or job request with evidence and dataset scope

#### Scenario: Retraining completes
- **WHEN** a retraining job produces a candidate model
- **THEN** the system SHALL record model metadata, comparison metrics, approval status, and rollback reference before it can become active
