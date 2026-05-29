# MCP Tools

The intended tool surface is deliberately narrow:

- `detect_regime`
- `compare_regimes`
- `scan_market`
- `propose_options_strategy`
- `check_portfolio_risk`
- `execute_trade`
- `get_live_monitoring`
- `retrain_clusters`
- `reflect_on_trade`

All tools use Pydantic input/output schemas under `src/regime_trader/mcp/schemas.py`. Authorization
requirements are declared in `src/regime_trader/mcp/auth.py`. Requests for shell, Python, SQL,
unrestricted HTTP, raw credentials, or unvalidated order placement are denied by
`src/regime_trader/mcp/deny.py` and audited.
