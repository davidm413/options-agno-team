from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from regime_trader.schemas.learning import PerformanceMetric, RetrainingJob


def evaluate_retraining_triggers(
    *,
    performance: tuple[PerformanceMetric, ...],
    active_model_version: str,
    model_created_at: datetime,
    max_model_age_days: int = 90,
) -> tuple[RetrainingJob, ...]:
    jobs: list[RetrainingJob] = []
    weak_groups = [metric for metric in performance if not metric.low_confidence and (metric.win_rate or 1) < 0.35]
    if weak_groups:
        jobs.append(
            RetrainingJob(
                job_id=f"retrain-{uuid4().hex}",
                trigger="performance_drift",
                evidence=tuple(metric.group_key for metric in weak_groups),
                dataset_scope="closed_trades_with_regime_features",
                rollback_model_version=active_model_version,
            )
        )
    if datetime.now(tz=UTC) - model_created_at > timedelta(days=max_model_age_days):
        jobs.append(
            RetrainingJob(
                job_id=f"retrain-{uuid4().hex}",
                trigger="stale_model_age",
                evidence=(f"model_age_days>{max_model_age_days}",),
                dataset_scope="latest_approved_historical_features",
                rollback_model_version=active_model_version,
            )
        )
    return tuple(jobs)
