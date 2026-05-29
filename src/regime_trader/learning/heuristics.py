from __future__ import annotations

from uuid import uuid4

from regime_trader.schemas.learning import (
    ApprovalStatus,
    LearnedHeuristic,
    PerformanceMetric,
    ReflectionResult,
)


def propose_heuristic(
    *,
    reflections: tuple[ReflectionResult, ...],
    performance: tuple[PerformanceMetric, ...],
    recommendation: str,
    affected_regimes: tuple[str, ...],
    proposed_config_change: dict[str, str],
) -> LearnedHeuristic:
    evidence = tuple(
        [reflection.reflection_id for reflection in reflections] + [metric.group_key for metric in performance]
    )
    return LearnedHeuristic(
        heuristic_id=f"heuristic-{uuid4().hex}",
        evidence_refs=evidence,
        affected_regimes=affected_regimes,
        recommendation=recommendation,
        proposed_config_change=proposed_config_change,
        approval_status=ApprovalStatus.PROPOSED,
    )


def approved_config_overrides(heuristics: tuple[LearnedHeuristic, ...]) -> dict[str, str]:
    overrides: dict[str, str] = {}
    for heuristic in heuristics:
        if heuristic.approval_status == ApprovalStatus.APPROVED:
            overrides.update(heuristic.proposed_config_change)
    return overrides
