CREATE TABLE IF NOT EXISTS audit_events (
    id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    symbol TEXT,
    payload_json TEXT NOT NULL,
    config_version TEXT,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS strategy_proposals (
    id TEXT PRIMARY KEY,
    symbol TEXT NOT NULL,
    strategy_type TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    config_version TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS risk_decisions (
    id TEXT PRIMARY KEY,
    proposal_id TEXT NOT NULL REFERENCES strategy_proposals(id),
    status TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS preflight_responses (
    id TEXT PRIMARY KEY,
    proposal_id TEXT NOT NULL REFERENCES strategy_proposals(id),
    status TEXT NOT NULL,
    provider TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS execution_records (
    id TEXT PRIMARY KEY,
    proposal_id TEXT NOT NULL REFERENCES strategy_proposals(id),
    status TEXT NOT NULL,
    mode TEXT NOT NULL,
    provider_order_id TEXT,
    payload_json TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS trade_journal (
    id TEXT PRIMARY KEY,
    symbol TEXT NOT NULL,
    strategy_type TEXT NOT NULL,
    entry_regime_label TEXT NOT NULL,
    realized_pnl NUMERIC(18, 4),
    payload_json TEXT NOT NULL,
    opened_at TIMESTAMPTZ NOT NULL,
    closed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS monitoring_alerts (
    id TEXT PRIMARY KEY,
    symbol TEXT NOT NULL,
    severity TEXT NOT NULL,
    reason TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS learned_heuristics (
    id TEXT PRIMARY KEY,
    approval_status TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS model_metadata (
    id BIGSERIAL PRIMARY KEY,
    model_version TEXT NOT NULL,
    approval_status TEXT NOT NULL,
    rollback_model_version TEXT,
    payload_json TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);
