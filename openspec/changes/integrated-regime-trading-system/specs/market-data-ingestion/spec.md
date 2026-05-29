## ADDED Requirements

### Requirement: Provider-neutral market data access
The system SHALL expose provider-neutral interfaces for market bars, quotes, option expirations, option chains, option Greeks, accounts, and positions, with Public.com implemented as the first provider.

#### Scenario: Fetch normalized bars through Public.com
- **WHEN** a caller requests bars for a configured symbol, interval, and lookback through the provider-neutral interface
- **THEN** the Public.com adapter SHALL fetch the provider data and return normalized bar records without exposing provider-specific response shapes to downstream engines

#### Scenario: Swap provider boundary remains stable
- **WHEN** a second provider adapter is added later
- **THEN** feature, regime, scanner, strategy, and monitoring modules SHALL continue consuming the same normalized interfaces and schemas

### Requirement: Normalized market and options schemas
The system SHALL normalize provider responses into typed schemas for bars, quotes, option contracts, option chains, Greeks, accounts, and positions.

#### Scenario: Normalize OHLCV data
- **WHEN** provider bar data is received
- **THEN** the system SHALL emit records containing symbol, timestamp, open, high, low, close, volume, interval, provider, and ingestion metadata

#### Scenario: Normalize options data
- **WHEN** provider option chain or Greeks data is received
- **THEN** the system SHALL emit records containing underlying symbol, expiration, strike, option type, bid, ask, mark or last price, implied volatility, Greeks where available, timestamp, and provider metadata

### Requirement: Market data freshness and quality checks
The system SHALL validate market data freshness, schema completeness, timestamp ordering, and missing-value policy before passing records to feature or strategy engines.

#### Scenario: Reject stale option chain
- **WHEN** an option chain response is older than the configured maximum age
- **THEN** the system SHALL mark it stale and prevent strategy generation from using it without an explicit stale-data override

#### Scenario: Detect gaps in bar history
- **WHEN** a requested bar history contains missing intervals or out-of-order timestamps
- **THEN** the system SHALL report a data quality issue and either backfill from the provider or return a structured rejection reason

### Requirement: Provider reliability controls
The system SHALL implement retries, provider rate-limit handling, request timeouts, idempotent reads, and cache-aware fallback for supported market data requests.

#### Scenario: Provider rate limit is reached
- **WHEN** the provider reports a rate-limit or retryable throttling response
- **THEN** the adapter SHALL respect the retry policy, avoid unbounded retries, and return a structured rate-limit status if the request cannot complete

#### Scenario: Cached data is allowed
- **WHEN** fresh provider data is unavailable and the caller permits cached data
- **THEN** the system SHALL return cached data only if it satisfies the caller's freshness and quality constraints

### Requirement: Streaming ingestion events
The system SHALL subscribe to available real-time provider streams and publish normalized quote, bar, and option update events to the internal event bus.

#### Scenario: Receive streaming quote update
- **WHEN** the Public.com WebSocket stream emits a quote update for a subscribed symbol
- **THEN** the data layer SHALL normalize the update and publish an internal event with symbol, timestamp, provider, payload type, and quality metadata

#### Scenario: Streaming interruption occurs
- **WHEN** a streaming connection is interrupted
- **THEN** the system SHALL reconnect according to policy, backfill missing intervals where possible, and emit a stream health event

### Requirement: Credential and secret handling
The system SHALL load provider credentials from approved secret sources and SHALL NOT persist or log raw credentials, tokens, or account secrets.

#### Scenario: Missing provider credential
- **WHEN** the Public.com adapter starts without required credentials
- **THEN** the adapter SHALL fail closed with a structured configuration error and SHALL NOT attempt unauthenticated provider calls

#### Scenario: Provider error is logged
- **WHEN** a provider call fails and the error is recorded
- **THEN** the log entry SHALL redact secrets and account tokens while preserving enough request metadata for debugging
