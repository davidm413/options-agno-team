# Architecture

The service is layered so deterministic code owns market transforms, regime labels, strategy
selection, risk checks, and execution gates. Agents and MCP tools orchestrate those services and
return typed JSON; they do not infer hidden state or expose arbitrary execution.

## Layers

- `data`: provider-neutral contracts, Public.com adapter, normalization, validation, retry/cache,
  and streaming event normalization.
- `features` and `regimes`: log returns, realized volatility, Wasserstein distance, entropy,
  option features, deterministic clustering, classifier rules, transitions, online updates, and
  retraining metadata.
- `scanner`: configured and explicit scans with per-symbol fault isolation, anomaly flags, and
  ranking.
- `trading`: strategy proposals, option leg filtering, risk review, preflight delegation, dry-run
  records, live execution gates, and position monitoring.
- `persistence`: Redis-style live state, Parquet snapshots, PostgreSQL models, event bus, audit
  records, and configuration versions.
- `mcp` and `agents`: narrow typed tool contracts, authorization, denied arbitrary capabilities,
  Agno role definitions, structured handoffs, and approved shared memory reads.
- `learning`: journal capture, reflection, performance-by-regime analytics, learned heuristics,
  approval gates, and retraining triggers.

Live trading remains disabled unless an operator deliberately enables it and clears the checklist in
`docs/operator-live-trading-checklist.md`.
