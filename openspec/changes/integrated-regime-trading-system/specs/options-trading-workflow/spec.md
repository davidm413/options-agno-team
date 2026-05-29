## ADDED Requirements

### Requirement: Regime-driven strategy proposal
The system SHALL convert approved regime outputs into one primary and at least one alternative options strategy proposal using configured strategy mapping rules.

#### Scenario: Bullish medium-volatility regime
- **WHEN** a symbol has a medium-volatility bullish regime with sufficient confidence
- **THEN** the strategy engine SHALL propose a defined-risk bullish options structure and include rationale, expected exposure, max loss, max gain where calculable, and rejection criteria

#### Scenario: Unstable high-entropy regime
- **WHEN** a regime output indicates high entropy or high Wasserstein instability
- **THEN** the strategy engine SHALL reduce sizing, widen defined-risk structures, propose neutral alternatives, or reject strategy generation according to configuration

### Requirement: Option contract selection
The system SHALL select option contracts from current option chain data using configurable expiration, strike, liquidity, bid-ask spread, delta, implied volatility, and risk filters.

#### Scenario: Select spread legs
- **WHEN** the strategy engine proposes a vertical spread
- **THEN** it SHALL select leg contracts that satisfy configured expiration, strike distance, liquidity, spread width, and max loss constraints

#### Scenario: No suitable contracts
- **WHEN** no contracts satisfy the configured filters for a strategy
- **THEN** the strategy engine SHALL return a no-trade result with failed filters and SHALL NOT fabricate contracts or prices

### Requirement: Portfolio risk review
The system SHALL require a portfolio risk decision before any strategy proposal can be submitted for provider preflight or execution.

#### Scenario: Approve within limits
- **WHEN** a strategy proposal stays within configured buying power, max loss, portfolio delta, position concentration, correlation, and open-trade limits
- **THEN** the risk engine SHALL approve it with sizing, rationale, and the exact limits evaluated

#### Scenario: Reject excessive risk
- **WHEN** a proposal exceeds any configured risk limit or lacks required market data
- **THEN** the risk engine SHALL reject it with structured reasons and SHALL prevent preflight and execution

### Requirement: Multi-leg preflight gate
The system SHALL run provider preflight for every live or execution-ready multi-leg options order before order placement.

#### Scenario: Preflight succeeds
- **WHEN** a risk-approved multi-leg strategy is submitted for execution
- **THEN** the execution layer SHALL call the provider preflight endpoint and record estimated cost, buying power requirement, commission where available, strategy name, and validation results before placement

#### Scenario: Preflight fails
- **WHEN** provider preflight rejects an order
- **THEN** the execution layer SHALL record the rejection and SHALL NOT place the order

### Requirement: Dry-run and live execution controls
The system SHALL default to dry-run execution and require explicit live-trading configuration before submitting any order to the provider.

#### Scenario: Dry-run execution
- **WHEN** execution is requested while live trading is disabled
- **THEN** the system SHALL create a dry-run execution record and SHALL NOT call the provider order placement endpoint

#### Scenario: Live execution enabled
- **WHEN** live trading is enabled and a preflight-approved execution request is submitted
- **THEN** the execution layer SHALL place the provider order with an idempotency key and persist the provider response

### Requirement: Position monitoring and exit recommendations
The system SHALL monitor open positions against live market data, regime shifts, P&L, Greeks, risk limits, and time-to-expiration rules.

#### Scenario: Regime shift breaches thesis
- **WHEN** an open position's current regime conflicts with the entry thesis beyond configured thresholds
- **THEN** the monitoring workflow SHALL produce a hold, close, roll, or hedge recommendation with rationale and required approval status

#### Scenario: Risk breach detected
- **WHEN** live P&L, Greeks, or portfolio exposure breaches configured limits
- **THEN** the monitoring workflow SHALL emit an alert and create a recommended risk action without automatically bypassing approval gates
