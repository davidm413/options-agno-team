from __future__ import annotations

from uuid import uuid4

from regime_trader.schemas.learning import ReflectionResult, ReflectionStatus, TradeJournalEntry


def reflect_on_trade(
    entry: TradeJournalEntry,
    *,
    exit_regime_label: str | None = None,
    outcome_notes: tuple[str, ...] = (),
) -> ReflectionResult:
    missing: list[str] = []
    if entry.realized_pnl is None:
        missing.append("realized_pnl")
    if exit_regime_label is None:
        missing.append("exit_regime_label")
    if missing:
        return ReflectionResult(
            reflection_id=f"reflection-{uuid4().hex}",
            journal_id=entry.journal_id,
            status=ReflectionStatus.INCOMPLETE,
            observations=tuple(outcome_notes),
            missing_data=tuple(missing),
        )
    observations = [
        f"entry_regime={entry.entry_regime_label}",
        f"exit_regime={exit_regime_label}",
        f"realized_pnl={entry.realized_pnl}",
        *outcome_notes,
    ]
    failures = ("thesis_regime_drift",) if exit_regime_label != entry.entry_regime_label else ()
    return ReflectionResult(
        reflection_id=f"reflection-{uuid4().hex}",
        journal_id=entry.journal_id,
        status=ReflectionStatus.COMPLETE,
        observations=tuple(observations),
        failure_modes=failures,
        improvement_candidates=("review_strategy_mapping",) if failures else (),
    )
