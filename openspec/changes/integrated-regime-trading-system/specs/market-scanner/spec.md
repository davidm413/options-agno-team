## ADDED Requirements

### Requirement: Configurable scan universe
The system SHALL scan only symbols and asset classes defined by configuration or explicit request input.

#### Scenario: Run configured scan
- **WHEN** a scan is started without an explicit symbol list
- **THEN** the scanner SHALL use the configured equities, options, and available crypto universe and SHALL record the configuration version used

#### Scenario: Run explicit symbol scan
- **WHEN** a caller provides an explicit symbol list and asset class
- **THEN** the scanner SHALL restrict data retrieval and regime analysis to that request scope

### Requirement: Regime ranking and comparison
The system SHALL return ranked scan results with regime labels, confidence, directional bias, anomaly scores, key drivers, and data quality status for each symbol.

#### Scenario: Compare option candidates
- **WHEN** a scan is run for options candidates
- **THEN** the scanner SHALL rank symbols using configured opportunity, confidence, risk, liquidity, and anomaly criteria

#### Scenario: Compare mixed assets
- **WHEN** a scan includes multiple asset classes
- **THEN** the scanner SHALL return comparable normalized regime summaries while preserving asset-class-specific metadata

### Requirement: Anomaly detection
The system SHALL detect sudden Wasserstein spikes, entropy jumps, volatility shifts, and stale or degraded data conditions during scans.

#### Scenario: Detect regime anomaly
- **WHEN** a symbol's Wasserstein distance or entropy change crosses configured anomaly thresholds
- **THEN** the scanner SHALL flag the symbol with anomaly type, severity, timestamp, and contributing features

#### Scenario: Degraded data impacts ranking
- **WHEN** a symbol has stale or incomplete market data
- **THEN** the scanner SHALL include a data quality warning and SHALL NOT rank the symbol above valid symbols solely on incomplete data

### Requirement: Scan fault isolation
The system SHALL isolate per-symbol provider, data quality, feature, and regime errors so one failed symbol does not fail the whole scan.

#### Scenario: One symbol fails
- **WHEN** a provider or feature error occurs for one symbol in a scan
- **THEN** the scanner SHALL return a structured error for that symbol and continue scanning the remaining symbols

#### Scenario: All symbols fail
- **WHEN** every symbol in a scan fails
- **THEN** the scanner SHALL return a failed scan status with per-symbol reasons and no partial success claim

### Requirement: Scheduled and on-demand scans
The system SHALL support on-demand scans and scheduled scans for pre-market, intraday, and end-of-day workflows.

#### Scenario: Scheduled intraday scan
- **WHEN** an intraday scan schedule triggers
- **THEN** the scanner SHALL run with the configured universe, publish scan results, and record scan metadata for monitoring and audit

#### Scenario: On-demand scan
- **WHEN** an authorized tool call requests a scan
- **THEN** the scanner SHALL execute immediately subject to provider rate limits and return a scan id with summarized results
