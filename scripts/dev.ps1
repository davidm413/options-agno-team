param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("lint", "format-check", "typecheck", "test", "readiness")]
    [string]$Task
)

switch ($Task) {
    "lint" { uv run ruff check . }
    "format-check" { uv run ruff format --check . }
    "typecheck" { uv run mypy src }
    "test" { uv run pytest }
    "readiness" { uv run regime-trader readiness --config config/sample.yaml }
}
