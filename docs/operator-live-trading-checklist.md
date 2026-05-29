# Live Trading Checklist

Live trading must remain disabled until every item below is completed and recorded.

- Confirm the Public.com account id and account owner context.
- Verify provider credentials are loaded from approved secret sources.
- Confirm `execution.live_trading_enabled` is deliberately set to `true`.
- Confirm kill-switch behavior and rollback steps are tested.
- Confirm risk limits for max loss, buying power fraction, open trades, concentration, and Greeks.
- Run dry-run workflows and review linked regime, proposal, risk, preflight, and execution records.
- Confirm every multi-leg order path calls `preflight_multileg` before placement.
- Confirm operator approval requirements for the target strategy classes.
- Confirm audit logging and persistence are healthy.
- Confirm no arbitrary shell, Python, SQL, HTTP, credential, or raw order tools are exposed.

Do not enable live placement if any checklist item is incomplete.
