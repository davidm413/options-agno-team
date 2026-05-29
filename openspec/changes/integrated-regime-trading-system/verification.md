# Verification

Date: 2026-05-29

Commands run:

- `uv run --extra dev ruff check .` -> passed
- `uv run --extra dev ruff format --check .` -> passed, 77 files already formatted
- `uv run --extra dev mypy src` -> passed, no issues found in 70 source files
- `uv run --extra dev pytest` -> passed, 11 tests passed
- `uv run regime-trader readiness --config config/sample.yaml` -> passed, status `ready`
- `python -m compileall src tests` -> passed

Notes:

- `uv run --extra dev ruff check .` created the local `.venv` and `uv.lock`.
- Live trading remains disabled in `config/sample.yaml`; readiness confirms dry-run mode and kill switch enabled.
