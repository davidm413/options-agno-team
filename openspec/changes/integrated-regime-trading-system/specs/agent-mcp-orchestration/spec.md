## ADDED Requirements

### Requirement: Typed MCP tool surface
The system SHALL expose a narrow set of typed MCP tools for regime detection, market scanning, strategy proposal, risk checks, execution, live monitoring, retraining, and trade reflection.

#### Scenario: Detect regime tool call
- **WHEN** an MCP client calls `detect_regime` with a valid symbol and configuration
- **THEN** the tool SHALL validate input, call deterministic services, and return typed JSON without exposing internal provider-specific objects

#### Scenario: Invalid tool input
- **WHEN** an MCP client submits missing or invalid fields
- **THEN** the tool SHALL reject the request with structured validation errors and SHALL NOT call downstream provider or execution services

### Requirement: No arbitrary execution tools
The system SHALL NOT expose arbitrary shell execution, arbitrary Python execution, unrestricted SQL, unrestricted HTTP, raw provider credentials, or unvalidated order placement through MCP or agents.

#### Scenario: Unsupported arbitrary command
- **WHEN** an agent or MCP client requests arbitrary code, SQL, shell, or HTTP execution
- **THEN** the system SHALL reject the request and log the denied capability without executing it

#### Scenario: Credential access requested
- **WHEN** an agent requests raw provider credentials or account secrets
- **THEN** the system SHALL deny the request and return only non-sensitive configuration status where appropriate

### Requirement: Agno agent roles
The system SHALL define separate Agno agents for regime detection, options strategy, risk and portfolio review, execution, monitoring, and learning.

#### Scenario: Strategy workflow orchestration
- **WHEN** a user or schedule requests an options trade candidate
- **THEN** the agent team SHALL run regime detection, strategy proposal, risk review, and execution readiness as separate steps with structured handoffs

#### Scenario: Execution agent receives unapproved proposal
- **WHEN** the execution agent receives a proposal without a positive risk decision and successful preflight
- **THEN** it SHALL reject execution and record the missing prerequisite

### Requirement: Shared memory boundaries
The system SHALL allow agents to read approved shared memory such as trade journal summaries, open position state, learned heuristics, and performance-by-regime metrics while preserving immutable audit records.

#### Scenario: Learning memory informs proposal
- **WHEN** the strategy agent evaluates a new proposal
- **THEN** it SHALL be able to read approved learned heuristics and performance summaries without modifying historical audit records

#### Scenario: Memory update from reflection
- **WHEN** the learning agent completes a post-trade reflection
- **THEN** it SHALL append a new learned-memory record with provenance instead of overwriting historical decisions

### Requirement: Tool authorization and audit
The system SHALL enforce authorization policies for tools that access account data, risk decisions, preflight, execution, retraining, or memory mutation.

#### Scenario: Unauthorized execution request
- **WHEN** a caller without execution permission invokes `execute_trade`
- **THEN** the MCP tool SHALL deny the request before provider preflight or placement and record an authorization failure

#### Scenario: Authorized retraining request
- **WHEN** an authorized caller invokes `retrain_clusters`
- **THEN** the tool SHALL validate dataset scope, create a training job record, and return status without blocking unrelated read-only tools
