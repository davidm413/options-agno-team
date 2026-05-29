## ADDED Requirements

### Requirement: Feature vector generation
The system SHALL generate clustering-ready feature vectors from normalized market and options data using deterministic feature functions.

#### Scenario: Build feature vector from market history
- **WHEN** normalized bar history satisfies the configured lookback and quality rules
- **THEN** the feature engine SHALL compute log returns, rolling realized volatility, Wasserstein distance, entropy, momentum, and a feature vector with feature names and values

#### Scenario: Include options-derived features
- **WHEN** valid option chain and Greeks data are available for a symbol
- **THEN** the feature engine SHALL include configured options-derived features such as implied volatility rank, skew, term structure slope, and strength metrics

### Requirement: Regime classification output
The system SHALL classify feature vectors into deterministic regime outputs containing volatility regime, directional bias, regime label, cluster id, confidence, key drivers, and source metadata.

#### Scenario: Classify symbol regime
- **WHEN** the regime engine receives a valid feature vector for a symbol
- **THEN** it SHALL return a structured regime output with symbol, timestamp, regime label, directional bias, confidence, key drivers, and feature/model version metadata

#### Scenario: Insufficient confidence
- **WHEN** the regime engine cannot classify a feature vector above the configured confidence threshold
- **THEN** it SHALL return an uncertain regime status with key drivers and SHALL prevent downstream strategy generation from treating the result as high confidence

### Requirement: Mathematical regime methods
The system SHALL support weighted clustering, Wasserstein distribution shift metrics, entropy metrics, and configurable classifier rules without relying on LLM judgment for core classification.

#### Scenario: Wasserstein spike detected
- **WHEN** current return distributions materially diverge from historical baseline distributions
- **THEN** the regime output SHALL include the Wasserstein distance and SHALL surface it as a key driver when it crosses configured thresholds

#### Scenario: Entropy changes risk interpretation
- **WHEN** entropy exceeds the configured uncertainty threshold
- **THEN** the regime output SHALL include the entropy value and indicate elevated uncertainty for downstream risk sizing

### Requirement: Transition state modeling
The system SHALL model regime persistence and transition probabilities for each symbol from historical classified states.

#### Scenario: Compute transition probability
- **WHEN** a symbol has sufficient classified regime history
- **THEN** the regime engine SHALL return transition probabilities such as probability of moving from risk-on to risk-off

#### Scenario: Insufficient transition history
- **WHEN** transition history is insufficient for a symbol
- **THEN** the regime engine SHALL return an explicit insufficient-history status for transition probabilities without failing the overall regime classification

### Requirement: Online updates and retraining
The system SHALL support lightweight online regime updates for streaming data and explicit retraining for heavier clustering or transition models.

#### Scenario: Streaming feature update
- **WHEN** new normalized market data arrives for a subscribed symbol
- **THEN** the regime engine SHALL update rolling features and emit a new regime state only when configured thresholds or intervals are met

#### Scenario: Retrain clusters
- **WHEN** an authorized caller requests cluster retraining with approved historical data
- **THEN** the system SHALL produce a new model version, persist training metadata, and keep the previous model version available for rollback

### Requirement: Reproducible regime decisions
The system SHALL persist enough metadata to reproduce each regime decision from input data, feature configuration, model version, and classifier configuration.

#### Scenario: Audit regime output
- **WHEN** an operator reviews a historical regime output
- **THEN** the system SHALL expose the input data window reference, feature values, model version, classifier rules version, and key drivers used to produce it
