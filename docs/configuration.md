# Configuration

`config/sample.yaml` shows the supported configuration sections:

- provider credential environment names and request controls
- scan universe symbols and asset classes
- feature windows and regime thresholds
- strategy mapping and option contract filters
- portfolio risk limits
- streaming thresholds
- Redis, PostgreSQL, and Parquet persistence paths
- execution mode, live-trading flag, approval requirement, and kill switch

Every `AppConfig` instance exposes a deterministic `version` hash. Decision records include that
version so historical behavior can be replayed against the configuration that produced it.
